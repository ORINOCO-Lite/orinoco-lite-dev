"""Portable staged-review evidence and a read-only model for the web interface."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile

from .errors import ConfigurationError
from .stage_reports import (
    VERSION, artifact_digest, canonical, json_digest, load_report, read_json,
    safe_artifact, validate_report, write_json,
)
from .stage_review import apply_changes, decision_for, load_decisions, summarize, validate_decisions


def value_views(finding: dict) -> dict:
    """Render JSON values before browser number parsing can erase their types.

    These strings are presentation data only. Reports, matching, and decisions
    continue to use the original typed values.
    """
    result = {}
    for side in ("before", "after"):
        if not finding[f"{side}_present"]:
            result[side] = {"type": "absent", "text": "<missing>"}
            continue
        value = finding[side]
        if value is None:
            kind = "null"
        elif isinstance(value, bool):
            kind = "boolean"
        elif isinstance(value, int):
            kind = "integer"
        elif isinstance(value, float):
            kind = "number"
        elif isinstance(value, str):
            kind = "string"
        elif isinstance(value, list):
            kind = f"array · {len(value)}"
        else:
            kind = f"object · {len(value)}"
        result[side] = {"type": kind,
                        "text": json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)}
    return result


def _present_row(row: dict) -> dict:
    result = deepcopy(row)
    result["value_views"] = value_views(row["finding"])
    return result


def _no_links(path: Path) -> Path:
    path = Path(path).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ConfigurationError(f"Review paths must not contain symbolic links: {component}")
    return path.resolve()


def _relative_review(paths: list[Path], decisions: dict, root: Path) -> dict:
    result = summarize(paths, decisions)
    locations = {}
    for path in paths:
        report, _ = load_report(path)
        for index, stage in enumerate(report["stages"]):
            for finding in stage["findings"]:
                locations[f"{report['run_id']}/{finding['id']}"] = (report["run_id"], index, stage["mode"])
    for row in result["findings"]:
        for key in ("report", "raw_evidence"):
            row[key] = Path(row[key]).resolve().relative_to(root).as_posix()
        row["run_id"], row["stage_index"], row["mode"] = locations[row["key"]]
    return result


def bundle(paths: list[Path], output: Path, decisions: Path | dict | None = None,
           title: str = "Staged comparison review") -> dict:
    """Copy only explicit validated reports and their evidence into a fresh directory.

    Application assets are supplied by the installed CLI when serving; bundle
    contents can never choose executable application code.
    """
    if not isinstance(title, str) or not title.strip():
        raise ConfigurationError("Review title must be nonempty text")
    if not paths:
        raise ConfigurationError("A review bundle requires at least one report")
    output = _no_links(output)
    if output.exists():
        raise ConfigurationError(f"Review output must be a fresh directory: {output}")
    snapshot = deepcopy(decisions) if isinstance(decisions, dict) else None
    protected = []
    if snapshot is None:
        if decisions is not None:
            decision_path = _no_links(Path(decisions))
            if not decision_path.is_file():
                raise ConfigurationError(f"Decision file is absent: {decision_path}")
            protected.append(decision_path)
        snapshot = load_decisions(Path(decisions) if decisions is not None else None)
    validate_decisions(snapshot)
    loaded, runs = [], set()
    for path in paths:
        path = _no_links(path)
        report, root = load_report(path)
        _no_links(root / "report.json" if path.is_dir() else path)
        if report["run_id"] in runs:
            raise ConfigurationError("The same report was supplied more than once")
        runs.add(report["run_id"])
        loaded.append((report, root))
        protected.append(root)
    if any(output == path or output in path.parents or path in output.parents for path in protected):
        raise ConfigurationError("Review output overlaps a report or decision input")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".review-bundle-", dir=output.parent) as temporary:
        target = Path(temporary) / "bundle"
        target.mkdir()
        report_paths = []
        for index, (report, source_root) in enumerate(loaded, start=1):
            destination = target / "reports" / f"{index:04d}"
            destination.mkdir(parents=True)
            names = {a["path"] for stage in report["stages"] for a in stage["artifacts"].values()}
            for relative in sorted(names, key=lambda name: (len(Path(name).parts), name)):
                source = safe_artifact(source_root, relative)
                copied = safe_artifact(destination, relative)
                if copied.exists():
                    continue  # A containing directory was already copied.
                copied.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, copied)
                else:
                    shutil.copyfile(source, copied)
            write_json(destination / "report.json", report)
            validate_report(report, destination)
            report_paths.append((destination / "report.json").relative_to(target).as_posix())
        review = _relative_review([target / path for path in report_paths], snapshot, target)
        document = {"schema_version": VERSION, "title": title.strip(), "report_paths": report_paths,
                    "decisions": snapshot, "base_digest": json_digest(snapshot), "review": review}
        write_json(target / "review.json", document)
        target.rename(output)
    return {"title": document["title"], "reports": len(report_paths),
            "base_digest": document["base_digest"], "counts": review["counts"],
            "path": str(output / "review.json")}


class ReviewModel:
    """Read copied evidence and preview decisions using the established matcher."""

    def __init__(self, bundle_path: Path):
        path = _no_links(bundle_path)
        self.root = path if path.is_dir() else path.parent
        source = self.root / "review.json" if path.is_dir() else path
        _no_links(source)
        data = read_json(source)
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != VERSION:
            raise ConfigurationError("Unsupported review bundle schema_version; expected 1")
        if not isinstance(data.get("title"), str) or not data["title"].strip():
            raise ConfigurationError("Review bundle requires a title")
        if not isinstance(data.get("report_paths"), list) or not data["report_paths"]:
            raise ConfigurationError("Review bundle requires report_paths")
        self.paths = [safe_artifact(self.root, value) for value in data["report_paths"]]
        if any(not path.is_file() for path in self.paths):
            raise ConfigurationError("Review report_paths must name report files")
        self.decisions = deepcopy(data.get("decisions"))
        validate_decisions(self.decisions)
        self.base_digest = json_digest(self.decisions)
        if data.get("base_digest") != self.base_digest:
            raise ConfigurationError("Review decision snapshot does not match its base digest")
        self.title = data["title"]
        self.reports = [load_report(path) for path in self.paths]
        self.review = _relative_review(self.paths, self.decisions, self.root)
        if canonical(data.get("review")) != canonical(self.review):
            raise ConfigurationError("Review summary differs from its reports and decision snapshot; rebuild the bundle")
        self._rows = {row["key"]: row for row in self.review["findings"]}
        self._stages = {(report["run_id"], index): (report, stage, root)
                        for report, root in self.reports for index, stage in enumerate(report["stages"])}

    def overview(self) -> dict:
        result = {key: deepcopy(self.review[key]) for key in (
            "counts", "groups", "data_flow", "incompatibilities", "integration", "integration_reason", "absent")}
        result.update(title=self.title, base_digest=self.base_digest, contexts=deepcopy(self.review["reports"]),
                      decisions=deepcopy(self.decisions),
                      decision_json={item["id"]: canonical(item) for item in self.decisions["decisions"]}, stages=[])
        for (run_id, index), (_, stage, root) in self._stages.items():
            item = {key: deepcopy(stage.get(key, [] if key in {"command", "diagnostics"} else None))
                    for key in ("stage", "scope", "status", "mode", "comparator", "command", "diagnostics", "artifacts")}
            item.update(run_id=run_id, stage_index=index)
            for artifact in item["artifacts"].values():
                artifact["path"] = safe_artifact(root, artifact["path"]).relative_to(self.root).as_posix()
            result["stages"].append(item)
        return result

    def findings(self, state: str = "new", stage: str = "", q: str = "", offset: int = 0, limit: int = 50,
                 *, run_id: str = "", stage_index: int | None = None) -> dict:
        if state not in {"all", "new", "changed", "matched", "outstanding", "queue"}:
            raise ConfigurationError("Unknown finding state")
        if not isinstance(stage, str) or not isinstance(q, str):
            raise ConfigurationError("Finding stage and search must be text")
        if not isinstance(run_id, str) or (stage_index is not None and (type(stage_index) is not int or stage_index < 0)):
            raise ConfigurationError("Finding run_id must be text and stage_index must be nonnegative")
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 500:
            raise ConfigurationError("Finding offset must be nonnegative and limit must be between 1 and 500")
        selected = []
        needle = q.casefold().strip()
        for row in self.review["findings"]:
            if (run_id and row["run_id"] != run_id) or (stage_index is not None and row["stage_index"] != stage_index):
                continue
            if state == "outstanding":
                if not row["decision"] or row["decision"]["disposition"] not in {"tolerated", "undecided"}:
                    continue
            elif state == "queue":
                if row["state"] not in {"new", "changed"}:
                    continue
            elif state != "all" and row["state"] != state:
                continue
            if stage and stage not in {row["finding"]["stage"], f"{row['run_id']}/{row['stage_index']}"}:
                continue
            if needle and needle not in canonical(row).casefold():
                continue
            selected.append(row)
        return {"items": [_present_row(row) for row in selected[offset:offset + limit]],
                "total": len(selected), "offset": offset, "limit": limit}

    def finding(self, key: str) -> dict:
        if not isinstance(key, str) or key not in self._rows:
            raise ConfigurationError("Unknown finding key")
        return _present_row(self._rows[key])

    def artifact_root(self, run_id: str, stage_index: int, role: str) -> Path:
        if type(stage_index) is not int or not isinstance(run_id, str) or not isinstance(role, str):
            raise ConfigurationError("Artifact selection requires run_id, integer stage_index, and role")
        entry = self._stages.get((run_id, stage_index))
        if entry is None or role not in entry[1]["artifacts"]:
            raise ConfigurationError("Unknown artifact selection")
        artifact = entry[1]["artifacts"][role]
        path = safe_artifact(entry[2], artifact["path"])
        if artifact_digest(path) != artifact["digest"]:
            raise ConfigurationError("Artifact changed since this review was opened")
        return path

    def decision(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ConfigurationError("Decision request must be an object")
        allowed = {"finding_key", "decision_id", "disposition", "rationale", "reconsider_when", "author", "rule"}
        if set(payload) - allowed:
            raise ConfigurationError("Decision requests cannot change scope or matching conditions directly")
        for field in ("author", "disposition", "rationale", "reconsider_when"):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                raise ConfigurationError(f"Decision requires nonempty {field}")
        existing = None
        if "decision_id" in payload:
            existing = next((d for d in self.decisions["decisions"] if d["id"] == payload["decision_id"]), None)
            if existing is None:
                raise ConfigurationError("Unknown decision ID")
        metadata = {field: payload[field].strip() for field in ("author", "disposition", "rationale", "reconsider_when")}
        if "finding_key" in payload:
            row = self.finding(payload["finding_key"])
            report, stage, _ = self._stages[row["run_id"], row["stage_index"]]
            result = decision_for(stage, row["finding"], report=report,
                                  rule=payload.get("rule", existing.get("rule") if existing else None), **metadata)
            if existing:
                if any(canonical(result.get(key)) != canonical(existing.get(key))
                       for key in ("stage", "subject", "location", "rule")):
                    raise ConfigurationError("A revised decision must preserve its exact selector and rule")
                result["id"] = existing["id"]
                result["input_conditions"] = deepcopy(existing["input_conditions"])
        elif existing:
            if "rule" in payload and payload["rule"] != existing.get("rule"):
                raise ConfigurationError("A revised decision must preserve its rule")
            result = {**deepcopy(existing), **metadata}
        else:
            raise ConfigurationError("Decision request requires finding_key or decision_id")
        validate_decisions({"schema_version": VERSION, "decisions": [result]})
        return result

    def preview(self, changes: dict) -> dict:
        updated = apply_changes(self.decisions, changes)
        result = _relative_review(self.paths, updated, self.root)
        diagnostics = list(result["incompatibilities"])
        diagnostics.extend(f"{stage['stage']}: {stage['status']}" for stage in result["stages"]
                           if stage["status"] != "complete")
        return {"changes": deepcopy(changes), "counts": result["counts"], "absent": result["absent"],
                "decision_count": len(updated["decisions"]), "diagnostics": diagnostics}

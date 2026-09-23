"""Portable evidence, scoped web decisions, and shared preview/write behavior."""

from argparse import Namespace
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from orinoco_lite.errors import ConfigurationError
from orinoco_lite import stage_bundle, stage_reports, stage_review
from orinoco_lite.stage_bundle import ReviewModel, bundle, value_views
from orinoco_lite.stage_reports import json_digest, read_json, write_json, write_report


@pytest.fixture(autouse=True)
def fixed_context(monkeypatch):
    monkeypatch.setattr(stage_reports, "execution_context", lambda: {"schema_digest": "selected-schema"})


def report(root, *, after="after", stage="storage", status="complete", scope=None, location=None):
    root.mkdir(parents=True)
    left, right = root / "left.json", root / "right.json"
    write_json(left, {"title": True})
    write_json(right, {"title": after})
    finding = {"subject": "ex:record", "location": location or ["title"], "change": "changed",
               "before": True, "after": after, "before_present": True, "after_present": True}
    path = root / "report"
    data = write_report(path, stage=stage, left=left, right=right, findings=[finding],
                        comparator="records-v1", status=status,
                        scope=scope or {"complete": True, "subjects": ["ex:record"], "all_locations": True},
                        diagnostics=["Retained diagnostic"] if status != "complete" else [])
    return path, data


def decision(data, disposition="tolerated"):
    stage = data["stages"][0]
    return stage_review.decision_for(stage, stage["findings"][0], report=data,
                                    disposition=disposition, rationale="Known difference",
                                    reconsider_when="Converter changes", author="Codex test")


def metadata(**values):
    return {"author": "Actual reviewer", "rationale": "Reviewed current evidence",
            "reconsider_when": "Next semantic change", "disposition": "intended", **values}


def edits(model, *items):
    return {"schema_version": 1, "base_digest": model.base_digest, "edits": list(items)}


@pytest.mark.parametrize("before,after,before_kind,after_kind,before_text,after_text", [
    (1, 1.0, "integer", "number", "1", "1.0"),
    ([1, 1.0], [1.0, 1], "array · 2", "array · 2", "[\n  1,\n  1.0\n]", "[\n  1.0,\n  1\n]"),
    ({"n": [1, 1.0]}, {"n": [1.0, 1]}, "object · 1", "object · 1",
     '{\n  "n": [\n    1,\n    1.0\n  ]\n}', '{\n  "n": [\n    1.0,\n    1\n  ]\n}'),
    (9007199254740993, -0.0, "integer", "number", "9007199254740993", "-0.0"),
    (True, "café", "boolean", "string", "true", '"café"'),
    (None, "null", "null", "string", "null", '"null"'),
])
def test_value_views_preserve_json_types_and_nested_number_spelling(before, after, before_kind, after_kind,
                                                                 before_text, after_text):
    finding = {"before": before, "after": after, "before_present": True, "after_present": True}
    views = value_views(finding)
    assert views == {"before": {"type": before_kind, "text": before_text},
                     "after": {"type": after_kind, "text": after_text}}
    assert stage_reports.canonical(json.loads(views["before"]["text"])) == stage_reports.canonical(before)
    assert stage_reports.canonical(json.loads(views["after"]["text"])) == stage_reports.canonical(after)


def test_value_views_distinguish_absence_from_present_null():
    finding = {"before": None, "after": None, "before_present": False, "after_present": True}
    assert value_views(finding) == {"before": {"type": "absent", "text": "<missing>"},
                                    "after": {"type": "null", "text": "null"}}


def test_returned_value_views_do_not_change_bundle_or_matching_values(tmp_path):
    source, data = report(tmp_path / "source", after=1.0)
    data["stages"][0]["findings"][0]["before"] = 1
    write_json(source / "report.json", data)
    output = tmp_path / "bundle"
    bundle([source], output)
    original = (output / "review.json").read_bytes()
    model = ReviewModel(output)
    row = model.findings()["items"][0]
    assert row["value_views"] == {"before": {"type": "integer", "text": "1"},
                                  "after": {"type": "number", "text": "1.0"}}
    assert model.finding(row["key"]) == row
    assert "value_views" not in model.review["findings"][0]
    assert (output / "review.json").read_bytes() == original
    assert "value_views" not in read_json(output / "review.json")["review"]["findings"][0]
    scoped = model.decision(metadata(finding_key=row["key"]))
    assert type(scoped["expected"]["before"]) is int
    assert type(scoped["expected"]["after"]) is float


def test_bundle_is_portable_and_does_not_copy_unreferenced_files(tmp_path):
    source, _ = report(tmp_path / "source", after=[True, 1, 1.0, None, "null"])
    (source / "secret-unreferenced.txt").write_text("excluded")
    output = tmp_path / "bundle"
    result = bundle([source], output, title="Portable evidence")
    assert result["counts"] == {"new": 1}
    document = read_json(output / "review.json")
    assert all(not Path(path).is_absolute() for path in document["report_paths"])
    assert not list(output.rglob("secret-unreferenced.txt"))
    assert not (output / "app").exists()
    moved = tmp_path / "moved"
    output.rename(moved)
    shutil.rmtree(source.parent)
    model = ReviewModel(moved)
    overview = model.overview()
    assert overview["title"] == "Portable evidence" and "findings" not in overview
    row = model.findings()["items"][0]
    assert row["finding"]["after"] == [True, 1, 1.0, None, "null"]
    assert not Path(row["report"]).is_absolute()
    artifact = model.artifact_root(row["run_id"], row["stage_index"], "left")
    assert artifact.is_relative_to(moved)
    assert read_json(artifact) == {"title": True}
    assert overview["stages"][0]["artifacts"]["left"]["digest"]


def test_model_matches_existing_cli_and_previews_changes_without_writes(tmp_path, capsys):
    source, data = report(tmp_path / "source")
    snapshot = {"schema_version": 1, "decisions": [decision(data)]}
    decisions = tmp_path / "decisions.json"
    write_json(decisions, snapshot)
    output = tmp_path / "bundle"
    bundle([source], output, decisions=decisions)
    model = ReviewModel(output)
    assert model.overview()["counts"] == stage_review.summarize([source], snapshot)["counts"]
    assert model.findings(state="outstanding")["total"] == 1
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    replacement = model.decision(metadata(decision_id=snapshot["decisions"][0]["id"]))
    changes = edits(model, {"action": "update", "id": replacement["id"], "decision": replacement})
    preview = model.preview(changes)
    assert preview["counts"] == {"matched": 1} and preview["decision_count"] == 1
    assert before == {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    changes_path = tmp_path / "decision-edits.json"
    write_json(changes_path, changes)
    assert stage_review.execute(Namespace(review_command="apply", directory=tmp_path, write=True)) == 0
    assert read_json(decisions) == stage_review.apply_changes(snapshot, changes)
    assert model.findings(state="outstanding")["total"] == 1  # Snapshot remains unchanged.
    capsys.readouterr()


def test_changed_behavior_can_be_reviewed_without_widening_selector(tmp_path):
    _, first = report(tmp_path / "first")
    source, _ = report(tmp_path / "current", after="changed behavior")
    prior = decision(first)
    prior["input_conditions"]["context"] = {"schema_digest": "selected-schema"}
    snapshot = {"schema_version": 1, "decisions": [prior]}
    output = tmp_path / "bundle"
    bundle([source], output, decisions=snapshot)
    model = ReviewModel(output)
    row = model.findings(state="queue")["items"][0]
    assert row["state"] == "changed"
    refreshed = model.decision(metadata(finding_key=row["key"], decision_id=prior["id"]))
    assert refreshed["expected"]["after"] == "changed behavior"
    assert refreshed["input_conditions"] == prior["input_conditions"]
    preview = model.preview(edits(model, {"id": prior["id"], "action": "update", "decision": refreshed}))
    assert preview["counts"] == {"matched": 1}
    other, _ = report(tmp_path / "other", location=["description"])
    another = tmp_path / "another-bundle"
    bundle([other], another, decisions=snapshot)
    model = ReviewModel(another)
    with pytest.raises(ConfigurationError, match="selector"):
        model.decision(metadata(finding_key=model.findings()["items"][0]["key"], decision_id=prior["id"]))


def test_state_stage_search_pagination_and_absent_decisions(tmp_path):
    a, first = report(tmp_path / "a")
    b, _ = report(tmp_path / "b", stage="rdf", after="Needle")
    c, _ = report(tmp_path / "c", stage="projection", status="failed")
    absent = decision(first)
    absent.update(id="absent", subject="ex:other")
    absent["input_conditions"]["scope"]["subject"] = "ex:other"
    output = tmp_path / "bundle"
    bundle([a, b, c], output, decisions={"schema_version": 1, "decisions": [decision(first), absent]})
    model = ReviewModel(output)
    assert model.findings(state="all", offset=1, limit=1)["total"] == 3
    assert len(model.findings(state="all", offset=1, limit=1)["items"]) == 1
    assert model.findings(state="queue")["total"] == 2
    assert model.findings(state="matched")["total"] == 1
    assert model.findings(state="outstanding")["total"] == 1
    row = model.findings(stage="rdf", q="nEedLe")["items"][0]
    assert model.findings(stage=f"{row['run_id']}/{row['stage_index']}")["total"] == 1
    assert model.findings(run_id=row["run_id"], stage_index=row["stage_index"])["items"] == [row]
    assert model.findings(run_id=row["run_id"], stage_index=99)["total"] == 0
    assert model.overview()["absent"][0]["state"] == "not-evaluated"
    assert "projection: failed" in model.preview(edits(model))["diagnostics"]
    removal = {"id": absent["id"], "action": "remove", "author": "Actual reviewer",
               "rationale": "Unpatched replay shows adaptation is no longer needed"}
    removed = model.preview(edits(model, removal))
    assert removed["decision_count"] == 1
    assert removed["changes"]["edits"][0] == removal
    with pytest.raises(ConfigurationError):
        model.findings(offset=-1)
    with pytest.raises(ConfigurationError):
        model.findings(limit=501)


def test_bundle_copies_tree_artifacts_with_exact_bytes(tmp_path):
    tree = tmp_path / "website"
    (tree / "nested").mkdir(parents=True)
    (tree / "nested/index.html").write_bytes(b"<script>untrusted()</script>\n")
    (tree / "logo.bin").write_bytes(bytes(range(256)))
    source = tmp_path / "report"
    write_report(source, stage="rendering", left=tree, right=tree, findings=[], comparator="site-files/1")
    output = tmp_path / "bundle"
    bundle([source], output)
    model = ReviewModel(output)
    stage = model.overview()["stages"][0]
    copied = model.artifact_root(stage["run_id"], 0, "left")
    assert (copied / "nested/index.html").read_bytes() == (tree / "nested/index.html").read_bytes()
    assert (copied / "logo.bin").read_bytes() == bytes(range(256))


def test_bundle_rejects_overlap_duplicate_missing_and_symbolic_paths(tmp_path):
    source, _ = report(tmp_path / "source")
    with pytest.raises(ConfigurationError, match="overlap"):
        bundle([source], source / "nested")
    with pytest.raises(ConfigurationError, match="same report"):
        bundle([source, source / "report.json"], tmp_path / "duplicate")
    with pytest.raises(ConfigurationError, match="absent"):
        bundle([source], tmp_path / "missing", decisions=tmp_path / "no-decisions.json")
    link = tmp_path / "link"
    link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ConfigurationError, match="symbolic"):
        bundle([link], tmp_path / "linked-source")
    with pytest.raises(ConfigurationError, match="overlap"):
        bundle([source], link / "linked-output")
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(ConfigurationError, match="fresh"):
        bundle([source], output)


@pytest.mark.parametrize("change", ["artifact", "report-path", "summary", "base", "version", "symlink"])
def test_model_rejects_tampered_or_unsupported_evidence(tmp_path, change):
    source, _ = report(tmp_path / "source")
    output = tmp_path / "bundle"
    bundle([source], output)
    data = read_json(output / "review.json")
    report_path = output / data["report_paths"][0]
    report_data = read_json(report_path)
    artifact = report_path.parent / report_data["stages"][0]["artifacts"]["left"]["path"]
    if change == "artifact":
        artifact.write_text("tampered")
    elif change == "symlink":
        artifact.unlink()
        artifact.symlink_to(tmp_path / "outside")
    elif change == "report-path":
        data["report_paths"][0] = "../source/report/report.json"
    elif change == "summary":
        data["review"]["findings"][0]["state"] = "matched"
    elif change == "base":
        data["base_digest"] = "stale"
    else:
        data["schema_version"] = 2
    write_json(output / "review.json", data)
    with pytest.raises(ConfigurationError):
        ReviewModel(output)


def test_decision_and_artifact_operations_fail_closed(tmp_path):
    source, data = report(tmp_path / "source")
    data["stages"][0]["findings"][0]["identity"] = "unmatched"
    write_json(source / "report.json", data)
    output = tmp_path / "bundle"
    bundle([source], output)
    model = ReviewModel(output)
    row = model.findings()["items"][0]
    with pytest.raises(ConfigurationError, match="ambiguous"):
        model.decision(metadata(finding_key=row["key"]))
    with pytest.raises(ConfigurationError, match="author"):
        model.decision(metadata(finding_key=row["key"], author="  "))
    with pytest.raises(ConfigurationError, match="scope"):
        model.decision(metadata(finding_key=row["key"], location=[]))
    with pytest.raises(ConfigurationError, match="stale"):
        model.preview({"schema_version": 1, "base_digest": "wrong", "edits": []})
    artifact = model.artifact_root(row["run_id"], row["stage_index"], "left")
    artifact.write_text("changed after opening")
    with pytest.raises(ConfigurationError, match="changed"):
        model.artifact_root(row["run_id"], row["stage_index"], "left")


@pytest.mark.parametrize("changes", [[], {"edits": None}, {"edits": [None]},
                                    {"edits": [{"id": "x", "action": "add"}]},
                                    {"edits": [{"id": "x", "action": "remove"}]}])
def test_apply_changes_rejects_malformed_edits_without_mutating_input(changes):
    snapshot = {"schema_version": 1, "decisions": []}
    original = deepcopy(snapshot)
    if isinstance(changes, dict):
        changes = {"schema_version": 1, "base_digest": json_digest(snapshot), **changes}
    with pytest.raises(ConfigurationError):
        stage_review.apply_changes(snapshot, changes)
    assert snapshot == original

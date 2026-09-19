from argparse import Namespace
from copy import deepcopy
from pathlib import Path

import pytest

from orinoco_lite.errors import ConfigurationError
from orinoco_lite.stage_reports import (
    artifact_digest, json_digest, load_report, read_json, write_json,
    write_operation, write_report,
)
from orinoco_lite.stage_review import decision_for, execute, summarize


def report(tmp_path, name="first", *, before="source", after="returned", status="complete",
           scope=None, stage="storage"):
    root = tmp_path / name
    root.mkdir()
    left, right = root / "source.json", root / "returned.json"
    write_json(left, {"title": before})
    write_json(right, {"title": after})
    findings = [] if before == after and type(before) is type(after) else [{
        "subject": "example:record", "location": ["title"], "change": "changed",
        "before": before, "after": after, "before_present": True, "after_present": True,
    }]
    destination = root / "report"
    data = write_report(destination, stage=stage, left=left, right=right, findings=findings,
                        comparator="records/1", status=status,
                        scope=scope or {"complete": True, "subjects": ["example:record"]})
    return destination, data


def decisions_for(data, disposition="tolerated"):
    stage = data["stages"][0]
    decision = decision_for(stage, stage["findings"][0], disposition=disposition,
                            rationale="Keep the known conversion limitation visible",
                            reconsider_when="The upstream converter preserves the source",
                            author="Codex (engineering exercise)", report=data)
    return {"schema_version": 1, "decisions": [decision]}


@pytest.mark.parametrize("disposition", ["intended", "tolerated", "undecided"])
def test_exact_decision_reused_after_repin_and_changed_value_reopens(tmp_path, disposition):
    first, data = report(tmp_path)
    decisions = decisions_for(data, disposition)
    second, new = report(tmp_path, "second")
    new["context"]["package_commit"] = "f" * 40
    write_json(second / "report.json", new)
    result = summarize([second], decisions)
    assert result["findings"][0]["state"] == "matched"
    assert result["findings"][0]["decision"]["disposition"] == disposition
    third, _ = report(tmp_path, "changed", after="different consequence")
    assert summarize([third], decisions)["findings"][0]["state"] == "changed"


@pytest.mark.parametrize("status,scope,expected_state", [
    ("complete", {"complete": True, "subjects": ["example:record"]}, "not-observed"),
    ("failed", {"complete": True, "subjects": ["example:record"]}, "not-evaluated"),
    ("skipped", {"complete": True, "subjects": ["example:record"]}, "not-evaluated"),
    ("complete", {"complete": True, "subjects": ["example:other"]}, "not-evaluated"),
    ("complete", {"complete": True, "subjects": ["example:record"], "locations": [["pid"]]}, "not-evaluated"),
])
def test_absence_requires_successful_coverage(tmp_path, status, scope, expected_state):
    _, data = report(tmp_path)
    next_report, _ = report(tmp_path, "next", after="source", status=status, scope=scope)
    result = summarize([next_report], decisions_for(data))
    assert result["absent"][0]["state"] == expected_state


def test_omitted_stage_is_not_evaluated(tmp_path):
    _, data = report(tmp_path)
    other, _ = report(tmp_path, "other", stage="rdf", after="source")
    assert summarize([other], decisions_for(data))["absent"][0]["state"] == "not-evaluated"


@pytest.mark.parametrize("before,after", [(1, True), (1, 1.0), (None, "null"), ([1, 1], [1]), ([1, 2], [2, 1])])
def test_decision_values_preserve_json_types_order_and_multiplicity(tmp_path, before, after):
    first, data = report(tmp_path, before=before, after=after)
    assert summarize([first], decisions_for(data))["findings"][0]["state"] == "matched"
    altered, _ = report(tmp_path, "altered", before=after, after=before)
    assert summarize([altered], decisions_for(data))["findings"][0]["state"] == "changed"


def test_conflicting_decisions_and_ambiguous_identity_reopen(tmp_path):
    source, data = report(tmp_path)
    decisions = decisions_for(data)
    duplicate = deepcopy(decisions["decisions"][0])
    duplicate["id"] = "second"
    decisions["decisions"].append(duplicate)
    assert summarize([source], decisions)["findings"][0]["state"] == "changed"
    decisions["decisions"].pop()
    data["stages"][0]["findings"][0]["identity"] = "ambiguous"
    write_json(source / "report.json", data)
    assert summarize([source], decisions)["findings"][0]["state"] == "changed"


def test_new_effect_stays_new_when_origin_matches(tmp_path):
    source, data = report(tmp_path)
    decisions = decisions_for(data)
    stage = data["stages"][0]
    effect = {**stage["findings"][0], "id": "storage:2", "subject": "page:a", "after": "new page"}
    stage["findings"].append(effect)
    stage["links"] = [{"origin": "storage:1", "effect": "storage:2", "status": "verified",
                       "replay": {"claim": "Input loss reaches page", "inputs": ["capture"],
                                  "operations": ["replay"], "outputs": ["page"], "artifact": "right"}}]
    write_json(source / "report.json", data)
    result = summarize([source], decisions)
    assert [row["state"] for row in result["findings"]] == ["matched", "new"]
    assert len(result["groups"]) == 1
    assert result["groups"][0]["status"] == "possible"
    assert len(result["findings"]) == 2


def test_tampered_missing_traversal_and_future_evidence_rejected(tmp_path):
    source, data = report(tmp_path)
    artifact = data["stages"][0]["artifacts"]["left"]
    original = deepcopy(data)
    artifact["path"] = "../source.json"
    write_json(source / "report.json", data)
    with pytest.raises(ConfigurationError, match="inside"):
        load_report(source)
    data = deepcopy(original)
    data["schema_version"] = 2
    write_json(source / "report.json", data)
    with pytest.raises(ConfigurationError, match="Unsupported"):
        load_report(source)
    write_json(source / "report.json", original)
    (source / original["stages"][0]["artifacts"]["left"]["path"]).write_text("changed")
    with pytest.raises(ConfigurationError, match="digest mismatch"):
        load_report(source)


def test_operation_links_require_matching_producer_not_only_bytes(tmp_path):
    capture = tmp_path / "capture.json"
    stored = tmp_path / "stored.json"
    projected = tmp_path / "projected.json"
    write_json(capture, {"a": 1})
    write_json(stored, {"a": 1})
    write_operation(stored, operation="records.convert", inputs={"capture": capture})
    write_json(projected, {"a": 1})
    write_operation(projected, operation="hugo.project", inputs={"records": stored})
    first = tmp_path / "storage"
    second = tmp_path / "projection"
    write_report(first, stage="storage", left=capture, right=stored, findings=[], comparator="records/1")
    write_report(second, stage="projection", left=stored, right=projected, findings=[], comparator="files/1")
    decisions = {"schema_version": 1, "decisions": []}
    result = summarize([first, second], decisions)
    assert any(link["status"] == "compatible" for link in result["data_flow"])
    assert result["incompatibilities"] == []
    data = read_json(first / "report.json")
    data["stages"][0]["artifacts"]["right"]["operation"]["operation"] = "other.converter"
    write_json(first / "report.json", data)
    data = read_json(second / "report.json")
    data["stages"][0]["artifacts"]["left"]["operation"]["operation"] = "other.converter"
    write_json(second / "report.json", data)
    result = summarize([first, second], decisions)
    assert result["incompatibilities"]
    assert result["integration"] == "not-established"


def test_decision_edits_preview_stale_digest_and_write_boundary(tmp_path, capsys):
    _, data = report(tmp_path)
    decisions = decisions_for(data)
    target = tmp_path / "decisions.json"
    write_json(target, decisions)
    before = target.read_bytes()
    changes = tmp_path / "changes.json"
    write_json(changes, {"schema_version": 1, "base_digest": json_digest(decisions),
                         "edits": [{"action": "remove", "id": decisions["decisions"][0]["id"]}]})
    args = Namespace(review_command="apply", decisions=target, changes=changes, write=False)
    assert execute(args) == 0
    assert target.read_bytes() == before
    args.write = True
    assert execute(args) == 0
    assert read_json(target)["decisions"] == []
    with pytest.raises(ConfigurationError, match="stale"):
        execute(args)


def test_directory_receipt_does_not_change_record_tree(tmp_path):
    records = tmp_path / "records"
    records.mkdir()
    (records / "record.yaml").write_text("title: hi\n")
    before = artifact_digest(records)
    write_operation(records, operation="records.convert", inputs={})
    assert list(records.iterdir()) == [records / "record.yaml"]
    assert artifact_digest(records) == before


def test_representation_rule_matches_only_its_tested_equivalence(tmp_path):
    source, data = report(tmp_path)
    stage = data["stages"][0]
    stage["comparator"] = "records-v1"
    stage["scope"].update(selection="all records", all_locations=True, exclusions=[])
    item = stage["findings"][0]
    item.update(comparator="records-v1", representation_equivalence="annotation-representation-v1")
    decision = decision_for(stage, item, disposition="intended", rationale="Equivalent attribution representation",
                            reconsider_when="Attribution or semantic values change", author="Codex", report=data,
                            rule="annotation-representation-v1")
    decisions = {"schema_version": 1, "decisions": [decision]}
    write_json(source / "report.json", data)
    assert summarize([source], decisions)["findings"][0]["state"] == "matched"
    item.pop("representation_equivalence")
    write_json(source / "report.json", data)
    assert summarize([source], decisions)["findings"][0]["state"] == "new"


def test_verified_replay_requires_actual_matching_operations_and_endpoints(tmp_path):
    import json
    inputs, outputs = [], []
    for name, value in (("first", 1), ("second", 2)):
        source, output = tmp_path / f"{name}-input.jsonl", tmp_path / f"{name}-output.json"
        source.write_text(json.dumps({"class_name": "XYZPublication", "record": {
            "pid": "record", "schema_type": "xyzri:XYZPublication", "title": str(value)}}) + "\n")
        write_json(output, {"display": str(value)})
        write_operation(output, operation="test.render", inputs={"records": source})
        inputs.append(source)
        outputs.append(output)
    finding = {"subject": "record", "location": ["title"], "change": "changed", "before": "1",
               "after": "2", "before_present": True, "after_present": True}
    origin_path = tmp_path / "origin"
    origin = write_report(origin_path, stage="storage", left=inputs[0], right=inputs[1],
                          findings=[finding], comparator="records-v1")
    replay = tmp_path / "replay.json"
    write_json(replay, {"schema_version": 1, "kind": "input-effect", "observations": [
        {"input": "input-left", "output": "left"}, {"input": "input-right", "output": "right"}]})
    effect_path = tmp_path / "effect"
    effect = write_report(effect_path, stage="projection", left=outputs[0], right=outputs[1],
                          findings=[finding], comparator="test/1", evidence={
                              "input-left": inputs[0], "input-right": inputs[1], "replay": replay})
    effect["stages"][0]["links"] = [{"origin": origin["run_id"] + "/storage:1", "effect": "projection:1",
                                     "status": "verified", "replay": {"artifact": "replay"}}]
    write_json(effect_path / "report.json", effect)
    decisions = {"schema_version": 1, "decisions": []}
    result = summarize([origin_path, effect_path], decisions)
    assert result["groups"][0]["status"] == "verified"
    assert all(row["state"] == "new" for row in result["findings"])
    effect["stages"][0]["artifacts"]["right"]["operation"]["operation"] = "other.render"
    write_json(effect_path / "report.json", effect)
    assert summarize([origin_path, effect_path], decisions)["groups"][0]["status"] == "possible"


def test_terminal_decision_saves_only_after_explicit_choice(tmp_path, monkeypatch, capsys):
    from orinoco_lite.stage_review import inspect_review
    source, _ = report(tmp_path)
    target = tmp_path / "decisions.json"
    replies = iter(["tolerated", "Known limitation", "Converter fix", "y", "quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(replies))
    assert inspect_review([source], target, "Codex") == 0
    saved = read_json(target)
    assert saved["decisions"][0]["disposition"] == "tolerated"
    assert summarize([source], saved)["findings"][0]["state"] == "matched"

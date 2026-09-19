"""Review exact, scoped diagnostic findings without changing raw comparisons."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
import uuid

from .errors import ConfigurationError
from .stage_reports import (
    VERSION, canonical, json_digest, load_report, read_json, safe_artifact, scope_text, write_json,
)


def register(subparsers) -> None:
    review = subparsers.add_parser("review", help="review staged comparisons and scoped decisions")
    commands = review.add_subparsers(dest="review_command", required=True)
    summarize = commands.add_parser("summarize", help="validate evidence and carry decisions into this review")
    summarize.add_argument("reports", nargs="+", type=Path)
    summarize.add_argument("--decisions", type=Path)
    summarize.add_argument("--output", type=Path, required=True)
    inspect = commands.add_parser("inspect", help="review findings and scoped decisions in the terminal")
    inspect.add_argument("reports", nargs="+", type=Path)
    inspect.add_argument("--decisions", type=Path, required=True)
    inspect.add_argument("--author", required=True)
    decide = commands.add_parser("decide", help="save one exact decision from a reviewed finding")
    decide.add_argument("report", type=Path)
    decide.add_argument("finding", help="run-local finding ID shown in the report")
    decide.add_argument("--decisions", type=Path, required=True)
    decide.add_argument("--disposition", choices=("intended", "tolerated", "undecided"), required=True)
    decide.add_argument("--rationale", required=True)
    decide.add_argument("--reconsider-when", required=True)
    decide.add_argument("--author", required=True, help="actual reviewer; agent judgments must name the agent")
    decide.add_argument("--equivalence-rule", choices=("annotation-representation-v1",),
                        help="review this tested representation rule across the selected stage")
    decide.add_argument("--write", action="store_true", help="write the previewed decision file")
    apply = commands.add_parser("apply", help="preview or apply decision edits against their original digest")
    apply.add_argument("changes", type=Path)
    apply.add_argument("--decisions", type=Path, required=True)
    apply.add_argument("--write", action="store_true")
    bundle = commands.add_parser("bundle", help="copy validated reports and decisions into a portable web review")
    bundle.add_argument("reports", nargs="+", type=Path)
    bundle.add_argument("--decisions", type=Path)
    bundle.add_argument("--output", type=Path, required=True)
    bundle.add_argument("--title", default="Staged comparison review")
    serve = commands.add_parser("serve", help="open a portable review on a local web server")
    serve.add_argument("directory", type=Path)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true", help="open the local review in your browser")


def expected(finding: dict) -> dict:
    return {"change": finding["change"],
            "before_present": finding.get("before_present", True),
            "after_present": finding.get("after_present", True),
            "before": finding.get("before"), "after": finding.get("after")}


def operations(stage: dict) -> dict:
    return {side: artifact["operation"]["operation"] if artifact.get("operation") else "supplied-input"
            for side, artifact in stage["artifacts"].items() if side in {"left", "right"}}


def compatibility(stage: dict, context: dict | None = None) -> dict:
    """A repin alone does not invalidate a decision; schema changes do."""
    schemas = {}
    for side, artifact in stage["artifacts"].items():
        if side not in {"left", "right"}:
            continue
        selected = (artifact.get("operation") or {}).get("context", {})
        schemas[side] = selected.get("schema_digest", (context or {}).get("schema_digest"))
    return {"schema_version": VERSION, "comparator": stage["comparator"], "schemas": schemas}


def validate_decisions(data: dict) -> None:
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != VERSION:
        raise ConfigurationError("Unsupported decision schema_version; expected 1")
    if not isinstance(data.get("decisions"), list):
        raise ConfigurationError("Decision file must contain a decisions list")
    seen = set()
    for decision in data["decisions"]:
        if not isinstance(decision, dict):
            raise ConfigurationError("Each decision must be an object")
        for field in ("id", "stage", "subject", "rationale", "reconsider_when", "author"):
            if not isinstance(decision.get(field), str) or not decision[field].strip():
                raise ConfigurationError(f"Decision requires nonempty {field}")
        if decision["id"] in seen:
            raise ConfigurationError(f"Duplicate decision ID: {decision['id']}")
        seen.add(decision["id"])
        if decision.get("disposition") not in {"intended", "tolerated", "undecided"}:
            raise ConfigurationError("Invalid decision disposition")
        if not isinstance(decision.get("location"), list) or any(type(x) not in (str, int) for x in decision["location"]):
            raise ConfigurationError("Decision requires a structured location")
        for field in ("expected", "operation", "compatibility", "input_conditions"):
            if not isinstance(decision.get(field), dict):
                raise ConfigurationError(f"Decision requires {field}")
        rule = decision.get("rule")
        if rule is not None:
            if (rule != "annotation-representation-v1" or decision["expected"] != {"representation_equivalence": rule}
                    or decision["subject"] != "*" or decision["location"] != []
                    or decision["compatibility"].get("comparator") != "records-v1"):
                raise ConfigurationError("Unsupported or incorrectly scoped representation rule")
        elif not {"change", "before", "after", "before_present", "after_present"} <= decision["expected"].keys():
            raise ConfigurationError("Decision expected change is incomplete")
        for field in (() if rule else ("before_present", "after_present")):
            if type(decision["expected"][field]) is not bool:
                raise ConfigurationError(f"Decision {field} must be boolean")
        conditions = decision["input_conditions"]
        if set(conditions) - {"scope", "context"} or not isinstance(conditions.get("scope"), dict):
            raise ConfigurationError("Input conditions support explicit scope and context only")
        expected_scope = ({"rule": rule, "selection": "all records", "exclusions": []} if rule else
                          {"subject": decision["subject"], "location": decision["location"]})
        if conditions["scope"] != expected_scope:
            raise ConfigurationError("Input condition scope must name the decision's exact subject and location")
        if not isinstance(conditions.get("context", {}), dict):
            raise ConfigurationError("Input condition context must be an object")
        canonical(decision)


def load_decisions(path: Path | None) -> dict:
    data = read_json(path) if path is not None and path.exists() else {"schema_version": VERSION, "decisions": []}
    validate_decisions(data)
    return data


def covers(stage: dict, decision: dict) -> bool:
    scope = stage["scope"]
    if stage["status"] != "complete" or scope.get("complete") is not True:
        return False
    if decision.get("rule"):
        return (scope.get("selection") == "all records" and scope.get("exclusions", []) == []
                and scope.get("all_locations") is not False)
    subject, location = decision["subject"], decision["location"]
    if subject in scope.get("exclusions", []):
        return False
    if not (scope.get("all_subjects") is True or subject in scope.get("subjects", [])):
        return False
    locations = scope.get("locations")
    if locations is None and scope.get("all_locations") is False:
        return False
    return locations is None or any(location[:len(prefix)] == prefix for prefix in locations)


def applies(stage: dict, context: dict, decision: dict) -> bool:
    if canonical(compatibility(stage, context)) != canonical(decision["compatibility"]):
        return False
    if operations(stage) != decision["operation"]:
        return False
    return all(key in context and canonical(context[key]) == canonical(value)
               for key, value in decision["input_conditions"].get("context", {}).items())


def decision_for(stage: dict, finding: dict, *, disposition: str, rationale: str,
                 reconsider_when: str, author: str, report: dict, rule: str | None = None) -> dict:
    if stage["status"] != "complete" or (not rule and finding.get("identity") in {"ambiguous", "unmatched"}):
        raise ConfigurationError("A failed comparison or ambiguous identity cannot support a reusable decision")
    data = {"id": str(uuid.uuid4()), "stage": stage["stage"],
            "subject": finding["subject"], "location": finding["location"],
            "disposition": disposition, "rationale": rationale,
            "operation": operations(stage), "expected": expected(finding),
            "compatibility": compatibility(stage, report["context"]),
            "input_conditions": {"scope": {"subject": finding["subject"], "location": finding["location"]}},
            "evidence": [{"run_id": report["run_id"], "finding": finding["id"]}],
            "reconsider_when": reconsider_when, "author": author}
    if rule:
        if finding.get("representation_equivalence") != rule:
            raise ConfigurationError("The selected finding does not satisfy this representation rule")
        data.update(rule=rule, subject="*", location=[], expected={"representation_equivalence": rule},
                    input_conditions={"scope": {"rule": rule, "selection": "all records", "exclusions": []}})
        if not covers(stage, data):
            raise ConfigurationError("Representation-rule decisions require a complete all-record comparison")
    validate_decisions({"schema_version": VERSION, "decisions": [data]})
    return data


def summarize(paths: list[Path], decisions: dict) -> dict:
    reports = [load_report(path) for path in paths]
    findings, entries, seen_decisions = [], [], set()
    run_ids = [report["run_id"] for report, _ in reports]
    if len(set(run_ids)) != len(run_ids):
        raise ConfigurationError("The same report was supplied more than once")
    for (report, root), source in zip(reports, paths):
        for stage in report["stages"]:
            entries.append((report, stage))
            for finding in stage["findings"]:
                candidates = [d for d in decisions["decisions"] if d["stage"] == stage["stage"] and (
                    (d.get("rule") and finding.get("representation_equivalence") == d["rule"])
                    or (not d.get("rule") and d["subject"] == finding["subject"]
                        and canonical(d["location"]) == canonical(finding["location"])))]
                exact = [d for d in candidates if stage["status"] == "complete"
                         and (d.get("rule") or finding.get("identity") not in {"ambiguous", "unmatched"})
                         and covers(stage, d) and applies(stage, report["context"], d)
                         and (d.get("rule") or canonical(d["expected"]) == canonical(expected(finding)))]
                # Even identically worded duplicate decisions are ambiguous ownership.
                state = "matched" if len(exact) == 1 and len(candidates) == 1 else "changed" if candidates else "new"
                seen_decisions.update(d["id"] for d in candidates)
                findings.append({"key": f"{report['run_id']}/{finding['id']}", "state": state,
                                 "finding": finding, "report": str(source),
                                 "decision": exact[0] if state == "matched" else None,
                                 "previous_decisions": [d["id"] for d in candidates],
                                 "raw_evidence": str(root / "report.json")})
    absent = []
    for decision in decisions["decisions"]:
        if decision["id"] in seen_decisions:
            continue
        relevant = [(r, s) for r, s in entries if s["stage"] == decision["stage"]]
        evaluated = any(covers(s, decision) and applies(s, r["context"], decision) for r, s in relevant)
        absent.append({"decision": decision, "state": "not-observed" if evaluated else "not-evaluated"})
    links, incompatibilities = data_flow(entries)
    groups, attribution_diagnostics = causal_groups(reports, findings)
    counts = Counter(row["state"] for row in findings + absent)
    return {"schema_version": VERSION, "reports": [{"run_id": r["run_id"], "context": r["context"]}
                                                   for r, _ in reports],
            "decisions_digest": json_digest(decisions), "findings": findings,
            "absent": absent, "counts": dict(counts), "groups": groups,
            "stages": [{"run_id": r["run_id"], "stage": s["stage"], "status": s["status"],
                        "scope": s["scope"], "mode": s["mode"]} for r, s in entries],
            "data_flow": links, "incompatibilities": incompatibilities + attribution_diagnostics,
            "integration": "not-established",
            "integration_reason": "Inspect explicit links and complete-path evidence; isolated agreement alone is insufficient."}


def data_flow(entries: list[tuple[dict, dict]]) -> tuple[list, list]:
    outputs = []
    for report, stage in entries:
        for side, artifact in stage["artifacts"].items():
            outputs.append((f"{report['run_id']}/{stage['stage']}/{side}", artifact, stage["status"]))
    links, problems = [], []
    for target, artifact, status in outputs:
        operation = artifact.get("operation")
        if not operation:
            continue
        for role, dependency in operation.get("inputs", {}).items():
            candidates = []
            for source, candidate, source_status in outputs:
                if source == target or candidate["digest"] != dependency.get("digest"):
                    continue
                producer = candidate.get("operation")
                producer_digest = json_digest(producer) if producer else None
                if dependency.get("producer") != producer_digest:
                    continue
                candidates.append((source, candidate, source_status))
            for source, candidate, source_status in candidates:
                valid = status == "complete" and source_status == "complete"
                links.append({"from": source, "to": target, "input": role,
                              "status": "compatible" if valid else "incompatible"})
                if not valid:
                    problems.append(f"{source} -> {target}: operation selection or completion differs")
            if not candidates and dependency.get("producer") and any(
                candidate["digest"] == dependency.get("digest") and candidate.get("operation")
                for source, candidate, _ in outputs if source != target
            ):
                problems.append(f"{target}/{role}: matching bytes exist but the selected producing operation is absent")
    return links, problems


def causal_groups(reports: list[tuple[dict, Path]], rows: list[dict]) -> tuple[list, list]:
    """Accept only this run's explicitly supplied replay evidence; never suppress raw rows."""
    known = {row["key"] for row in rows}
    finding_by_key = {row["key"]: row["finding"] for row in rows}
    stages = {f"{report['run_id']}/{finding['id']}": stage
              for report, _ in reports for stage in report["stages"] for finding in stage["findings"]}
    groups, diagnostics = [], []
    for report, root in reports:
      for stage in report["stages"]:
        for link in stage.get("links", []):
            origin = link.get("origin", "")
            effect = link.get("effect", "")
            if "/" not in origin:
                origin = f"{report['run_id']}/{origin}"
            if "/" not in effect:
                effect = f"{report['run_id']}/{effect}"
            if origin not in known or effect not in known:
                diagnostics.append("Attribution refers to a finding outside its run")
                continue
            evidence = link.get("replay", {})
            verified = False
            role = evidence.get("artifact")
            if link.get("status") == "verified" and role in stage["artifacts"] and stage["status"] == "complete":
                replay = read_json(safe_artifact(root, stage["artifacts"][role]["path"]))
                verified = verify_input_replay(replay, stage, stages[origin], stages[effect],
                                               root=root, origin_finding=finding_by_key[origin])
                if not verified:
                    diagnostics.append(f"Replay does not establish the claimed attribution: {origin} -> {effect}")
            groups.append({"origin": origin, "effect": effect,
                           "status": "verified" if verified else "possible", "replay": evidence})
    return groups, diagnostics


def verify_input_replay(replay: dict, evidence_stage: dict, origin: dict, effect: dict,
                        *, root: Path, origin_finding: dict) -> bool:
    """Verify a two-input replay through an unchanged operation.

    General causal claims stay possible. This narrow rule requires actual
    operation receipts and ties both replay endpoints to the reported stages.
    """
    if not isinstance(replay, dict) or replay.get("schema_version") != VERSION or replay.get("kind") != "input-effect":
        return False
    if origin["status"] != "complete" or effect["status"] != "complete":
        return False
    observations = replay.get("observations")
    if not isinstance(observations, list) or len(observations) != 2:
        return False
    selected = []
    for side, observation in zip(("left", "right"), observations):
        if not isinstance(observation, dict):
            return False
        inputs = evidence_stage["artifacts"].get(observation.get("input"))
        output = evidence_stage["artifacts"].get(observation.get("output"))
        if not inputs or not output or not output.get("operation"):
            return False
        operation = output["operation"]
        if inputs["digest"] != origin["artifacts"][side]["digest"] or output["digest"] != effect["artifacts"][side]["digest"]:
            return False
        dependencies = operation.get("inputs", {})
        if not any(d.get("digest") == inputs["digest"] and d.get("producer") == (
            json_digest(inputs["operation"]) if inputs.get("operation") else None
        ) for d in dependencies.values()):
            return False
        selected.append((operation, inputs, output))
    first, second = selected
    # A whole-stream swap with many differences does not prove which assertion
    # caused the effect. Require a selective record replay for verified links.
    if origin["comparator"] != "records-v1":
        return False
    from .record_stages import compare_records
    from .upstream_snapshot import load_jsonl, SnapshotError
    try:
        differences = compare_records(load_jsonl(safe_artifact(root, first[1]["path"])),
                                      load_jsonl(safe_artifact(root, second[1]["path"])))
    except (SnapshotError, ConfigurationError):
        return False
    if not differences or any(d["subject"] != origin_finding["subject"] or
                              d["location"][:len(origin_finding["location"])] != origin_finding["location"]
                              for d in differences):
        return False
    # The relevant code/schema/context and every non-varied input must agree.
    if first[0]["operation"] != second[0]["operation"] or canonical(first[0].get("context")) != canonical(second[0].get("context")):
        return False
    def held(operation, varied):
        return {k: v for k, v in operation["inputs"].items() if v["digest"] != varied["digest"]}
    return (canonical(held(first[0], first[1])) == canonical(held(second[0], second[1]))
            and first[1]["digest"] != second[1]["digest"]
            and first[2]["digest"] != second[2]["digest"])


def render_summary(result: dict) -> str:
    lines = ["# Staged comparison review", "", "Raw comparison findings remain unchanged.", "",
             "States: " + canonical(result["counts"]), ""]
    for stage in result["stages"]:
        lines.append(f"- {stage['stage']}: {stage['status']} ({stage['mode']}); scope {scope_text(stage['scope'])}")
    lines += ["", f"Integration: {result['integration']}. {result['integration_reason']}", ""]
    for group in result["groups"]:
        lines.append(f"Attribution ({group['status']}): {group['origin']} -> {group['effect']}")
    for problem in result["incompatibilities"]:
        lines.append(f"INCOMPLETE: {problem}")
    def brief(value):
        text = canonical(value)
        return text if len(text) < 400 else text[:397] + "... (full value in raw evidence)"

    matched_rules = Counter(row["decision"]["id"] for row in result["findings"]
                            if row.get("decision") and row["decision"].get("rule"))
    displayed_rules, displayed = set(), Counter()
    for row in result["findings"]:
        finding, decision = row["finding"], row["decision"]
        if decision and decision.get("rule"):
            if decision["id"] in displayed_rules:
                continue
            displayed_rules.add(decision["id"])
            lines += ["", f"## matched/{decision['disposition']}: {decision['rule']}",
                      f"{matched_rules[decision['id']]} raw findings satisfy this reviewed representation rule.",
                      f"Decision by {decision['author']}: {decision['rationale']}",
                      f"Reconsider when: {decision['reconsider_when']}",
                      f"All findings remain in review.json and {row['raw_evidence']}."]
            continue
        label = row["state"]
        if decision:
            label += "/" + decision["disposition"]
            if decision["disposition"] in {"tolerated", "undecided"}:
                label += " (outstanding)"
        displayed[label] += 1
        if displayed[label] > 30:
            continue
        lines += ["", f"## {label}: {finding['subject']} {canonical(finding['location'])}",
                  f"Boundary: {finding['first_boundary']}; change: {finding['change']}",
                  "Before: " + (brief(finding.get("before")) if finding.get("before_present", True) else "<missing>"),
                  "After: " + (brief(finding.get("after")) if finding.get("after_present", True) else "<missing>"),
                  f"Evidence: {row['raw_evidence']}; finding {finding['id']}"]
        if decision:
            lines += [f"Decision by {decision['author']}: {decision['rationale']}",
                      f"Reconsider when: {decision['reconsider_when']}"]
        else:
            lines.append("Next action: inspect evidence, fix/report, or record a scoped decision.")
    for label, count in displayed.items():
        if count > 30:
            lines += ["", f"{label}: showing 30 of {count}. Every finding and full value is retained in review.json and raw reports."]
    for row in result["absent"]:
        lines += ["", f"{row['state']}: decision {row['decision']['id']}"]
        if row["state"] == "not-observed":
            lines.append("Retirement candidate only; test without the adaptation before removing it.")
    return "\n".join(lines) + "\n"


def apply_changes(decisions: dict, changes: dict) -> dict:
    """Validate an exported edit document and return a new decision snapshot."""
    validate_decisions(decisions)
    if (not isinstance(changes, dict) or type(changes.get("schema_version")) is not int
            or changes["schema_version"] != VERSION or changes.get("base_digest") != json_digest(decisions)):
        raise ConfigurationError("Decision edits are stale or unsupported; reopen against the current decision file")
    if not isinstance(changes.get("edits"), list):
        raise ConfigurationError("Decision edits must be a list")
    by_id = {d["id"]: deepcopy(d) for d in decisions["decisions"]}
    touched = set()
    for edit in changes["edits"]:
        if not isinstance(edit, dict):
            raise ConfigurationError("Each decision edit must be an object")
        key, action = edit.get("id"), edit.get("action")
        if not isinstance(key, str) or not key.strip() or key in touched:
            raise ConfigurationError("Each decision edit must have one unique ID")
        touched.add(key)
        if action == "remove" and key in by_id:
            del by_id[key]
            continue
        if not ((action == "add" and key not in by_id) or (action == "update" and key in by_id)):
            raise ConfigurationError(f"Invalid {action} for decision {key}")
        value = edit.get("decision")
        if not isinstance(value, dict) or value.get("id") != key:
            raise ConfigurationError("Edit ID differs from decision ID")
        by_id[key] = deepcopy(value)
    updated = {"schema_version": VERSION, "decisions": list(by_id.values())}
    validate_decisions(updated)
    return updated


def execute(args) -> int:
    if args.review_command == "bundle":
        from .stage_bundle import bundle
        print(canonical(bundle(args.reports, args.output, decisions=args.decisions, title=args.title)))
        return 0
    if args.review_command == "serve":
        from .stage_web import serve
        serve(args.directory, port=args.port, open_browser=args.open)
        return 0
    if args.review_command == "inspect":
        return inspect_review(args.reports, args.decisions, args.author)
    decisions = load_decisions(args.decisions)
    if args.review_command == "summarize":
        if args.decisions is not None and not args.decisions.is_file():
            raise ConfigurationError(f"Decision file is absent: {args.decisions}")
        destinations = [(args.output / name).resolve() for name in ("review.json", "summary.md")]
        protected = [args.decisions.resolve()] if args.decisions else []
        for path in args.reports:
            report, root = load_report(path)
            protected.extend([root.resolve() / "report.json", root.resolve() / "summary.md"])
            protected.extend(safe_artifact(root, a["path"]).resolve()
                             for s in report["stages"] for a in s["artifacts"].values())
        if any(destination == source or source in destination.parents for destination in destinations for source in protected):
            raise ConfigurationError("Review output overlaps a report, artifact, or decision input")
        result = summarize(args.reports, decisions)
        args.output.mkdir(parents=True, exist_ok=True)
        write_json(args.output / "review.json", result)
        text = render_summary(result)
        (args.output / "summary.md").write_text(text, encoding="utf-8")
        print(text)
        return 0
    if args.review_command == "decide":
        report, _ = load_report(args.report)
        selected = [(s, f) for s in report["stages"] for f in s["findings"] if f["id"] == args.finding]
        if len(selected) != 1:
            raise ConfigurationError(f"Finding must identify exactly one report item: {args.finding}")
        stage, finding = selected[0]
        decision = decision_for(stage, finding, disposition=args.disposition, rationale=args.rationale,
                                reconsider_when=args.reconsider_when, author=args.author, report=report,
                                rule=getattr(args, "equivalence_rule", None))
        updated = {"schema_version": VERSION, "decisions": [*decisions["decisions"], decision]}
    else:
        updated = apply_changes(decisions, read_json(args.changes))
    validate_decisions(updated)
    print(canonical(updated))
    if args.write:
        write_json(args.decisions, updated)
        print(f"Wrote {args.decisions}; inspect its Git diff before committing.")
    else:
        print("Preview only; pass --write to save this decision file.")
    return 0


def inspect_review(paths: list[Path], decision_path: Path, author: str) -> int:
    """A small line-oriented review interface over the same matcher as summarize."""
    decisions = load_decisions(decision_path)
    expected_digest = json_digest(decisions)
    selected_stage = None
    position = 0
    while True:
        result = summarize(paths, decisions)
        rows = [row for row in result["findings"] if selected_stage is None or row["finding"]["stage"] == selected_stage]
        rows.sort(key=lambda row: ({"new": 0, "changed": 1, "matched": 2}[row["state"]], row["key"]))
        print("\nReview states: " + canonical(result["counts"]))
        print("Stages: " + ", ".join(sorted({s["stage"] for s in result["stages"]})))
        if rows:
            position %= len(rows)
            row = rows[position]
            finding = row["finding"]
            print(f"[{position + 1}/{len(rows)}] {row['state']} " + canonical({
                "stage": finding["stage"], "subject": finding["subject"], "location": finding["location"]}))
            print("Before/after: " + canonical(expected(finding)))
            print("Evidence: " + row["raw_evidence"])
            if row["decision"]:
                print("Decision: " + canonical(row["decision"]))
        else:
            print("No current findings in this selection; absent decision states: " +
                  canonical([{ "id": item["decision"]["id"], "state": item["state"]} for item in result["absent"]]))
        try:
            command = input("next / previous / stage NAME / all / intended / tolerated / undecided / rule / quit > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nReview closed.")
            return 0
        if command in {"q", "quit"}:
            return 0
        if command in {"", "next", "n"}:
            position += 1
        elif command in {"previous", "p"}:
            position -= 1
        elif command.startswith("stage "):
            selected_stage, position = command[6:], 0
        elif command == "all":
            selected_stage, position = None, 0
        elif rows and command in {"intended", "tolerated", "undecided", "rule"}:
            if row["decision"]:
                print("This finding already has a decision. Use review apply to revise it with a checked base digest.")
                continue
            disposition, rule = command, None
            if command == "rule":
                rule = finding.get("representation_equivalence")
                if rule != "annotation-representation-v1":
                    print("This finding has no supported representation rule.")
                    continue
                disposition = "intended"
            try:
                rationale = input("Reason > ").strip()
                reconsider = input("Reconsider or remove when > ").strip()
                if not rationale or not reconsider:
                    print("Both reason and reconsideration condition are required; nothing saved.")
                    continue
                report, _ = load_report(Path(row["report"]))
                stage = next(s for s in report["stages"] if s["stage"] == finding["stage"])
                decision = decision_for(stage, finding, disposition=disposition, rationale=rationale,
                                        reconsider_when=reconsider, author=author, report=report, rule=rule)
                print(canonical(decision))
                if input("Save this exact decision? [y/N] > ").strip().lower() != "y":
                    continue
                if json_digest(load_decisions(decision_path)) != expected_digest:
                    raise ConfigurationError("Decision file changed during this review; reopen before saving")
                decisions = {"schema_version": VERSION, "decisions": [*decisions["decisions"], decision]}
                validate_decisions(decisions)
                write_json(decision_path, decisions)
                expected_digest = json_digest(decisions)
                print(f"Saved {decision_path}; inspect its Git diff. Raw reports are unchanged.")
            except (EOFError, KeyboardInterrupt):
                print("\nDecision cancelled.")
            except ConfigurationError as error:
                print(error)
        else:
            print("Choose a listed command.")

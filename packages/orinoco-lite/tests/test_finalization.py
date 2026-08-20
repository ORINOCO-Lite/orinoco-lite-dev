from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from orinoco_lite.annotations import annotation_companion, assertion_sha256
from orinoco_lite.candidates import Candidate, CandidatePlan
from orinoco_lite.canonical import canonical_yaml_bytes
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.finalization import _copy_finalized_paths, finalize_candidate_plan


NAMESPACE = "https://source.example/records"
AGENT = "xyzrins:source-adapters/example/v1"


def record(pid: str, name: str, **values: object) -> dict[str, object]:
    return {
        "schema_type": "xyzri:XYZOrganization",
        "pid": pid,
        "name": name,
        **values,
    }


def provenance(
    pid: str,
    value: object,
    *,
    path: str = "/name",
    imported_from: str = f"{NAMESPACE}/one",
) -> dict[str, object]:
    return annotation_companion(
        pid,
        [
            {
                "path": path,
                "assertion_sha256": assertion_sha256(value),
                "pav:importedBy": AGENT,
                "pav:importedFrom": imported_from,
            }
        ],
    )


def candidate(
    source_id: str,
    pid: str,
    *,
    baseline: Mapping[str, object] | None,
    proposed: Mapping[str, object] | None,
    baseline_companion: Mapping[str, object] | None = None,
    proposed_companion: Mapping[str, object] | None = None,
) -> Candidate:
    return Candidate(
        source_namespace=NAMESPACE,
        source_record_id=source_id,
        pid=pid,
        record_path=f"XYZOrganization/{source_id}.yaml",
        baseline_record=baseline,
        proposed_record=proposed,
        baseline_companion=baseline_companion,
        proposed_companion=proposed_companion,
        source_claim={"name": "source", "source_id": source_id},
    )


class GitRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.mkdir()
        self.git("init", "--quiet", "--initial-branch=main")
        self.git("config", "user.name", "Test Curator")
        self.git("config", "user.email", "curator@example.test")
        self.git("config", "commit.gpgsign", "false")

    def git(
        self,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        completed = subprocess.run(
            ("git", "-C", str(self.path), *arguments),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and completed.returncode != 0:
            raise AssertionError(
                f"git {' '.join(arguments)} failed:\n"
                + completed.stderr.decode("utf-8", "replace")
            )
        return completed

    @property
    def head(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.decode().strip()

    def write_bytes(self, path: str, value: bytes) -> None:
        target = self.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)

    def write(self, path: str, value: Mapping[str, object]) -> None:
        self.write_bytes(path, canonical_yaml_bytes(value))

    def remove(self, path: str) -> None:
        (self.path / path).unlink()

    def commit(self, message: str) -> str:
        self.git("add", "--all")
        self.git(
            "commit",
            "--quiet",
            "--allow-empty",
            "--no-gpg-sign",
            "-m",
            message,
        )
        return self.head

    def status(self) -> bytes:
        return self.git(
            "status", "--porcelain=v1", "-z", "--untracked-files=all"
        ).stdout


class FinalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = GitRepository(Path(self.temporary.name) / "repository")

    def plan(
        self,
        base: str,
        candidates: Sequence[Candidate],
    ) -> CandidatePlan:
        return CandidatePlan(
            adapter="example",
            adapter_version="1.0.0",
            adapter_agent_pid=AGENT,
            source_namespace=NAMESPACE,
            source_coordinate={"revision": "source-v1"},
            metadata_base=base,
            candidates=candidates,
        )

    def apply_plan(self, plan: CandidatePlan) -> str:
        for change in plan.file_changes():
            if change.proposed is None:
                self.repo.remove(change.path)
            else:
                self.repo.write_bytes(change.path, change.proposed)
        return self.repo.commit("proposal")

    def finalize(
        self,
        plan: CandidatePlan,
        proposal: str,
        dispositions: Mapping[str, str],
        *,
        submitted_head: str | None = None,
    ):
        return finalize_candidate_plan(
            self.repo.path,
            plan=plan,
            proposal_commit=proposal,
            submitted_head=submitted_head or self.repo.head,
            dispositions=dispositions,
        )

    def test_all_rejected_restores_add_modify_delete_and_preserves_human_edit(
        self,
    ) -> None:
        add_pid = "xyzrins:records/add"
        modify_pid = "xyzrins:records/modify"
        delete_pid = "xyzrins:records/delete"
        stable_fields = {
            f"slot_{index:02d}": f"stable-{index}" for index in range(12)
        }
        old_modify = record(
            modify_pid,
            "old",
            **stable_fields,
            z_review_note="before review",
        )
        old_delete = record(delete_pid, "keep on rejection")
        self.repo.write("metadata/records/XYZOrganization/modify.yaml", old_modify)
        self.repo.write("metadata/records/XYZOrganization/delete.yaml", old_delete)
        self.repo.write_bytes("README.md", b"outside metadata\n")
        base = self.repo.commit("base")
        items = (
            candidate(
                "add",
                add_pid,
                baseline=None,
                proposed=record(add_pid, "source addition"),
            ),
            candidate(
                "modify",
                modify_pid,
                baseline=old_modify,
                proposed=record(
                    modify_pid,
                    "source modification",
                    **stable_fields,
                    z_review_note="before review",
                ),
            ),
            candidate(
                "delete",
                delete_pid,
                baseline=old_delete,
                proposed=None,
            ),
        )
        plan = self.plan(base, items)
        proposal = self.apply_plan(plan)

        self.repo.write(
            "metadata/records/XYZOrganization/modify.yaml",
            record(
                modify_pid,
                "source modification",
                **stable_fields,
                z_review_note="human addition",
            ),
        )
        self.repo.commit("human non-overlap")

        result = self.finalize(
            plan,
            proposal,
            {item.pid: "reject" for item in items},
        )

        self.assertFalse(
            (self.repo.path / "metadata/records/XYZOrganization/add.yaml").exists()
        )
        self.assertEqual(
            (self.repo.path / "metadata/records/XYZOrganization/modify.yaml").read_bytes(),
            canonical_yaml_bytes(
                record(
                    modify_pid,
                    "old",
                    **stable_fields,
                    z_review_note="human addition",
                )
            ),
        )
        self.assertEqual(
            (self.repo.path / "metadata/records/XYZOrganization/delete.yaml").read_bytes(),
            canonical_yaml_bytes(old_delete),
        )
        self.assertEqual((self.repo.path / "README.md").read_bytes(), b"outside metadata\n")
        self.assertEqual(
            result.changed_paths,
            (
                "metadata/records/XYZOrganization/add.yaml",
                "metadata/records/XYZOrganization/delete.yaml",
                "metadata/records/XYZOrganization/modify.yaml",
            ),
        )
        self.assertTrue(result.metadata_changed)
        self.assertTrue(
            all(
                path.startswith(("metadata/records/", "metadata/overlays/annotations/"))
                for path in result.changed_paths
            )
        )

    def test_defer_uses_the_same_non_overlapping_reverse_patch(self) -> None:
        pid = "xyzrins:records/defer"
        stable_fields = {
            f"slot_{index:02d}": f"stable-{index}" for index in range(12)
        }
        baseline = record(
            pid,
            "old",
            **stable_fields,
            z_review_note="before review",
        )
        self.repo.write("metadata/records/XYZOrganization/defer.yaml", baseline)
        base = self.repo.commit("base")
        item = candidate(
            "defer",
            pid,
            baseline=baseline,
            proposed=record(
                pid,
                "source",
                **stable_fields,
                z_review_note="before review",
            ),
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        self.repo.write(
            item.record_repository_path,
            record(
                pid,
                "source",
                **stable_fields,
                z_review_note="human",
            ),
        )
        self.repo.commit("human non-overlap")

        result = self.finalize(plan, proposal, {pid: "defer"})

        self.assertEqual(
            (self.repo.path / item.record_repository_path).read_bytes(),
            canonical_yaml_bytes(
                record(
                    pid,
                    "old",
                    **stable_fields,
                    z_review_note="human",
                )
            ),
        )
        self.assertEqual(result.changed_paths, (item.record_repository_path,))

    def test_overlapping_rejection_fails_without_touching_the_worktree(self) -> None:
        pid = "xyzrins:records/overlap"
        baseline = record(pid, "old")
        self.repo.write("metadata/records/XYZOrganization/overlap.yaml", baseline)
        base = self.repo.commit("base")
        item = candidate(
            "overlap",
            pid,
            baseline=baseline,
            proposed=record(pid, "source"),
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        human = canonical_yaml_bytes(record(pid, "human correction"))
        self.repo.write_bytes(item.record_repository_path, human)
        self.repo.commit("human overlap")

        with self.assertRaisesRegex(ConfigurationError, "overlaps submitted-head"):
            self.finalize(plan, proposal, {pid: "reject"})

        self.assertEqual(
            (self.repo.path / item.record_repository_path).read_bytes(), human
        )
        self.assertEqual(self.repo.status(), b"")

    def test_all_accept_is_an_explicit_cache_only_signal(self) -> None:
        pid = "xyzrins:records/accept"
        self.repo.write_bytes("README.md", b"sentinel\n")
        base = self.repo.commit("base")
        item = candidate(
            "accept",
            pid,
            baseline=None,
            proposed=record(pid, "source"),
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)

        result = self.finalize(plan, proposal, {pid: "accept"})

        self.assertEqual(result.changed_paths, ())
        self.assertFalse(result.metadata_changed)
        self.assertEqual(self.repo.status(), b"")
        self.assertEqual((self.repo.path / "README.md").read_bytes(), b"sentinel\n")

    def test_accepted_human_correction_drops_only_stale_proposal_pav(self) -> None:
        pid = "xyzrins:records/corrected"
        proposed_record = record(pid, "source")
        proposed_companion = provenance(pid, "source")
        base = self.repo.commit("base")
        item = candidate(
            "corrected",
            pid,
            baseline=None,
            proposed=proposed_record,
            proposed_companion=proposed_companion,
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        correction = canonical_yaml_bytes(record(pid, "human correction"))
        self.repo.write_bytes(item.record_repository_path, correction)
        self.repo.commit("human correction")

        result = self.finalize(plan, proposal, {pid: "accept"})

        self.assertEqual(
            (self.repo.path / item.record_repository_path).read_bytes(), correction
        )
        self.assertFalse(
            (self.repo.path / item.companion_repository_path).exists()
        )
        self.assertEqual(result.changed_paths, (item.companion_repository_path,))
        self.assertTrue(result.metadata_changed)

    def test_reconciliation_preserves_valid_human_added_companion_assertion(
        self,
    ) -> None:
        pid = "xyzrins:records/human-provenance"
        proposed_record = record(pid, "source")
        proposed_companion = provenance(pid, "source")
        base = self.repo.commit("base")
        item = candidate(
            "human-provenance",
            pid,
            baseline=None,
            proposed=proposed_record,
            proposed_companion=proposed_companion,
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        human_record = record(pid, "human correction", description="curated")
        human_assertion = {
            "path": "/description",
            "assertion_sha256": assertion_sha256("curated"),
            "pav:importedBy": "xyzrins:curators/human",
            "pav:importedFrom": "https://human.example/review",
        }
        proposal_assertions = proposed_companion["assertions"]
        self.assertIsInstance(proposal_assertions, list)
        current_companion = annotation_companion(
            pid,
            [*proposal_assertions, human_assertion],
        )
        self.repo.write(item.record_repository_path, human_record)
        self.repo.write(item.companion_repository_path, current_companion)
        self.repo.commit("human record and companion correction")

        result = self.finalize(plan, proposal, {pid: "accept"})

        self.assertEqual(
            (self.repo.path / item.record_repository_path).read_bytes(),
            canonical_yaml_bytes(human_record),
        )
        self.assertEqual(
            (self.repo.path / item.companion_repository_path).read_bytes(),
            canonical_yaml_bytes(annotation_companion(pid, [human_assertion])),
        )
        self.assertEqual(result.changed_paths, (item.companion_repository_path,))

    def test_missing_stale_proposal_companion_is_already_reconciled(self) -> None:
        pid = "xyzrins:records/already-reconciled"
        proposed_record = record(pid, "source")
        base = self.repo.commit("base")
        item = candidate(
            "already-reconciled",
            pid,
            baseline=None,
            proposed=proposed_record,
            proposed_companion=provenance(pid, "source"),
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        self.repo.write(item.record_repository_path, record(pid, "human correction"))
        self.repo.remove(item.companion_repository_path)
        self.repo.commit("human removes stale provenance")

        result = self.finalize(plan, proposal, {pid: "accept"})

        self.assertEqual(result.changed_paths, ())
        self.assertFalse(result.metadata_changed)
        self.assertEqual(self.repo.status(), b"")

    def test_accepted_empty_companion_is_deleted(self) -> None:
        pid = "xyzrins:records/empty"
        proposed = record(pid, "source")
        base = self.repo.commit("base")
        item = candidate(
            "empty",
            pid,
            baseline=None,
            proposed=proposed,
            proposed_companion=annotation_companion(pid, []),
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)

        result = self.finalize(plan, proposal, {pid: "accept"})

        self.assertFalse(
            (self.repo.path / item.companion_repository_path).exists()
        )
        self.assertEqual(result.changed_paths, (item.companion_repository_path,))

    def test_changed_or_stale_non_proposal_companion_fails_closed(self) -> None:
        changed_pid = "xyzrins:records/changed-companion"
        changed_record = record(changed_pid, "source")
        base = self.repo.commit("base")
        changed_item = candidate(
            "changed-companion",
            changed_pid,
            baseline=None,
            proposed=changed_record,
            proposed_companion=provenance(changed_pid, "source"),
        )
        changed_plan = self.plan(base, (changed_item,))
        changed_proposal = self.apply_plan(changed_plan)
        self.repo.write(
            changed_item.companion_repository_path,
            provenance(
                changed_pid,
                "source",
                imported_from="https://human.example/replacement",
            ),
        )
        self.repo.commit("human companion change")

        with self.assertRaisesRegex(ConfigurationError, "changed a reviewed assertion"):
            self.finalize(changed_plan, changed_proposal, {changed_pid: "accept"})
        self.assertEqual(self.repo.status(), b"")

        stale_root = Path(self.temporary.name) / "stale-repository"
        stale_repo = GitRepository(stale_root)
        old_record = record("xyzrins:records/stale", "old", description="old")
        old_companion = provenance("xyzrins:records/stale", "old")
        stale_repo.write("metadata/records/XYZOrganization/stale.yaml", old_record)
        stale_repo.write(
            "metadata/overlays/annotations/XYZOrganization/stale.yaml",
            old_companion,
        )
        stale_base = stale_repo.commit("base")
        stale_item = candidate(
            "stale",
            "xyzrins:records/stale",
            baseline=old_record,
            proposed=record(
                "xyzrins:records/stale", "old", description="source change"
            ),
            baseline_companion=old_companion,
            proposed_companion=old_companion,
        )
        stale_plan = self.plan(stale_base, (stale_item,))
        for change in stale_plan.file_changes():
            if change.proposed is None:
                stale_repo.remove(change.path)
            else:
                stale_repo.write_bytes(change.path, change.proposed)
        stale_proposal = stale_repo.commit("proposal")
        stale_repo.write(
            stale_item.record_repository_path,
            record(
                "xyzrins:records/stale",
                "human correction",
                description="source change",
            ),
        )
        stale_head = stale_repo.commit("human correction")

        with self.assertRaisesRegex(ConfigurationError, "stale non-proposal"):
            finalize_candidate_plan(
                stale_repo.path,
                plan=stale_plan,
                proposal_commit=stale_proposal,
                submitted_head=stale_head,
                dispositions={stale_item.pid: "accept"},
            )
        self.assertEqual(stale_repo.status(), b"")

    def test_ambiguous_proposal_selector_fails_without_guessing(self) -> None:
        pid = "xyzrins:records/ambiguous"
        alias = {"name": "same"}
        proposed = record(pid, "source", aliases=[alias])
        companion = provenance(pid, alias, path="/aliases")
        base = self.repo.commit("base")
        item = candidate(
            "ambiguous",
            pid,
            baseline=None,
            proposed=proposed,
            proposed_companion=companion,
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        self.repo.write(item.record_repository_path, record(pid, "source", aliases=[alias, alias]))
        self.repo.commit("ambiguous human correction")

        with self.assertRaisesRegex(ConfigurationError, "ambiguous"):
            self.finalize(plan, proposal, {pid: "accept"})

        self.assertEqual(self.repo.status(), b"")

    def test_stale_submitted_head_and_wrong_metadata_base_are_rejected(self) -> None:
        pid = "xyzrins:records/stale-head"
        stale_base = self.repo.commit("earlier base")
        base = self.repo.commit("base")
        item = candidate(
            "stale-head",
            pid,
            baseline=None,
            proposed=record(pid, "source"),
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        self.repo.write_bytes("review-note.txt", b"new head\n")
        current = self.repo.commit("human review")

        with self.assertRaisesRegex(ConfigurationError, "Submitted head is stale"):
            self.finalize(
                plan,
                proposal,
                {pid: "accept"},
                submitted_head=proposal,
            )

        wrong_plan = self.plan(stale_base, (item,))
        with self.assertRaisesRegex(ConfigurationError, "Proposal must be exactly one"):
            finalize_candidate_plan(
                self.repo.path,
                plan=wrong_plan,
                proposal_commit=proposal,
                submitted_head=current,
                dispositions={pid: "accept"},
            )
        self.assertEqual(self.repo.status(), b"")

    def test_proposal_must_be_one_exact_canonical_candidate_only_commit(self) -> None:
        pid = "xyzrins:records/malformed"
        base = self.repo.commit("base")
        item = candidate(
            "malformed",
            pid,
            baseline=None,
            proposed=record(pid, "source"),
        )
        plan = self.plan(base, (item,))
        self.repo.write_bytes(
            item.record_repository_path,
            b"schema_type: xyzri:XYZOrganization\npid: xyzrins:records/malformed\n"
            b"name: source\n",
        )
        malformed = self.repo.commit("noncanonical proposal")

        with self.assertRaisesRegex(ConfigurationError, "not the regenerated canonical"):
            self.finalize(plan, malformed, {pid: "accept"})
        self.assertEqual(self.repo.status(), b"")

        outside_root = Path(self.temporary.name) / "outside-proposal"
        outside_repo = GitRepository(outside_root)
        outside_base = outside_repo.commit("base")
        outside_item = candidate(
            "malformed",
            pid,
            baseline=None,
            proposed=record(pid, "source"),
        )
        outside_plan = self.plan(outside_base, (outside_item,))
        for change in outside_plan.file_changes():
            if change.proposed is not None:
                outside_repo.write_bytes(change.path, change.proposed)
        outside_repo.write_bytes("unexpected.txt", b"must not be proposed\n")
        outside_proposal = outside_repo.commit("proposal with extra path")

        with self.assertRaisesRegex(ConfigurationError, "unexpected unexpected.txt"):
            finalize_candidate_plan(
                outside_repo.path,
                plan=outside_plan,
                proposal_commit=outside_proposal,
                submitted_head=outside_proposal,
                dispositions={pid: "accept"},
            )
        self.assertEqual(
            (outside_repo.path / "unexpected.txt").read_bytes(),
            b"must not be proposed\n",
        )
        self.assertEqual(outside_repo.status(), b"")

    def test_semantic_base_verification_allows_formatting_but_rejects_drift(self) -> None:
        pid = "xyzrins:records/base"
        baseline = record(pid, "old")
        base_path = "metadata/records/XYZOrganization/base.yaml"
        self.repo.write_bytes(
            base_path,
            b"schema_type: xyzri:XYZOrganization\npid: xyzrins:records/base\nname: old\n",
        )
        base = self.repo.commit("noncanonical but semantic base")
        item = candidate(
            "base",
            pid,
            baseline=baseline,
            proposed=record(pid, "source"),
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)

        result = self.finalize(plan, proposal, {pid: "reject"})

        self.assertTrue(result.metadata_changed)
        self.assertEqual(
            (self.repo.path / base_path).read_bytes(),
            b"schema_type: xyzri:XYZOrganization\npid: xyzrins:records/base\nname: old\n",
        )

        drift_root = Path(self.temporary.name) / "drift-repository"
        drift_repo = GitRepository(drift_root)
        drift_repo.write(
            base_path,
            record(pid, "different base"),
        )
        drift_base = drift_repo.commit("drift base")
        drift_plan = self.plan(drift_base, (item,))
        for change in drift_plan.file_changes():
            if change.proposed is not None:
                drift_repo.write_bytes(change.path, change.proposed)
        drift_proposal = drift_repo.commit("proposal")

        with self.assertRaisesRegex(ConfigurationError, "does not match Git semantics"):
            finalize_candidate_plan(
                drift_repo.path,
                plan=drift_plan,
                proposal_commit=drift_proposal,
                submitted_head=drift_proposal,
                dispositions={pid: "accept"},
            )
        self.assertEqual(drift_repo.status(), b"")

    def test_incomplete_decisions_and_dirty_worktrees_fail_before_writing(self) -> None:
        one = candidate(
            "one",
            "xyzrins:records/one",
            baseline=None,
            proposed=record("xyzrins:records/one", "one"),
        )
        two = candidate(
            "two",
            "xyzrins:records/two",
            baseline=None,
            proposed=record("xyzrins:records/two", "two"),
        )
        base = self.repo.commit("base")
        plan = self.plan(base, (one, two))
        proposal = self.apply_plan(plan)

        with self.assertRaisesRegex(ConfigurationError, "missing xyzrins:records/two"):
            self.finalize(plan, proposal, {one.pid: "accept"})

        self.repo.write_bytes("untracked.txt", b"dirty\n")
        with self.assertRaisesRegex(ConfigurationError, "clean worktree"):
            self.finalize(
                plan,
                proposal,
                {one.pid: "accept", two.pid: "accept"},
            )
        self.assertEqual((self.repo.path / "untracked.txt").read_bytes(), b"dirty\n")

    def test_empty_candidate_plan_cannot_finalize_an_empty_proposal(self) -> None:
        base = self.repo.commit("base")
        plan = self.plan(base, ())
        proposal = self.repo.commit("empty proposal")

        with self.assertRaisesRegex(ConfigurationError, "at least one"):
            self.finalize(plan, proposal, {})

        self.assertEqual(self.repo.status(), b"")

    def test_inherited_git_control_environment_cannot_redirect_operations(self) -> None:
        pid = "xyzrins:records/environment"
        base = self.repo.commit("base")
        item = candidate(
            "environment",
            pid,
            baseline=None,
            proposed=record(pid, "source"),
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        submitted = self.repo.head

        with mock.patch.dict(
            os.environ,
            {
                "GIT_DIR": str(Path(self.temporary.name) / "not-a-repository"),
                "GIT_WORK_TREE": str(Path(self.temporary.name) / "wrong-worktree"),
                "GIT_INDEX_FILE": str(Path(self.temporary.name) / "wrong-index"),
                "GIT_OBJECT_DIRECTORY": str(Path(self.temporary.name) / "objects"),
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(
                    Path(self.temporary.name) / "alternate"
                ),
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.bare",
                "GIT_CONFIG_VALUE_0": "true",
            },
        ):
            result = self.finalize(
                plan,
                proposal,
                {pid: "accept"},
                submitted_head=submitted,
            )

        self.assertFalse(result.metadata_changed)
        self.assertEqual(self.repo.status(), b"")

    def test_symlinked_candidate_parent_cannot_escape_reject_rehearsal(self) -> None:
        pid = "xyzrins:records/symlink"
        baseline = record(pid, "base")
        path = "metadata/records/XYZOrganization/symlink.yaml"
        self.repo.write(path, baseline)
        base = self.repo.commit("base")
        item = candidate(
            "symlink",
            pid,
            baseline=baseline,
            proposed=None,
        )
        plan = self.plan(base, (item,))
        proposal = self.apply_plan(plan)
        parent = self.repo.path / "metadata/records/XYZOrganization"
        parent.rmdir()
        external = Path(self.temporary.name) / "external"
        external.mkdir()
        external_record = external / "symlink.yaml"
        external_record.write_bytes(b"outside\n")
        parent.symlink_to(external, target_is_directory=True)
        self.repo.commit("human symlink parent")

        with self.assertRaisesRegex(ConfigurationError, "parent is not a regular"):
            self.finalize(plan, proposal, {pid: "reject"})

        self.assertEqual(external_record.read_bytes(), b"outside\n")
        self.assertEqual(self.repo.status(), b"")

    def test_copy_preflight_rejects_symlink_destination_without_partial_write(
        self,
    ) -> None:
        rehearsal = Path(self.temporary.name) / "rehearsal"
        caller = Path(self.temporary.name) / "caller"
        external = Path(self.temporary.name) / "copy-external"
        rehearsal_path = rehearsal / "metadata/records/Type/one.yaml"
        rehearsal_path.parent.mkdir(parents=True)
        rehearsal_path.write_bytes(b"finalized\n")
        caller_parent = caller / "metadata/records"
        caller_parent.mkdir(parents=True)
        external.mkdir()
        external_file = external / "one.yaml"
        external_file.write_bytes(b"outside\n")
        (caller_parent / "Type").symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(ConfigurationError, "parent is not a regular"):
            _copy_finalized_paths(
                rehearsal,
                caller,
                ("metadata/records/Type/one.yaml",),
            )

        self.assertEqual(external_file.read_bytes(), b"outside\n")


if __name__ == "__main__":
    unittest.main()

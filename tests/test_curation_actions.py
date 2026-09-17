"""Observable failure boundaries for coordinated adapter publication."""
from unittest.mock import Mock
import subprocess

import pytest

from orinoco_lite import curation_actions


@pytest.fixture
def publication(monkeypatch):
    context = {
        "repository": "example/site", "metadata_repository": "example/metadata",
        "branch": "automation/curation/1", "head": "a" * 40,
        "metadata_head": "b" * 40, "result": "c" * 40,
        "metadata_result": "d" * 40, "comment_id": 7, "number": 8,
        "metadata": {"pull_request": 9},
    }
    website = {"head": {"sha": context["head"]}, "state": "open", "draft": True}
    metadata = {"head": {"sha": context["metadata_head"], "ref": "metadata-review"},
                "state": "open", "draft": True}
    monkeypatch.setenv("GH_TOKEN", "website-token")
    monkeypatch.setenv("METADATA_TOKEN", "metadata-token")
    monkeypatch.setattr(curation_actions, "api", Mock(side_effect=[website, metadata]))
    git = Mock()
    monkeypatch.setattr(curation_actions, "git", git)
    return context, website, metadata, git


@pytest.mark.parametrize("target", ["website", "metadata"])
def test_stale_repository_stops_before_either_push(publication, target):
    context, website, metadata, git = publication
    (website if target == "website" else metadata)["head"]["sha"] = "e" * 40
    with pytest.raises(RuntimeError, match="head changed"):
        curation_actions.publish(context)
    git.assert_not_called()


def test_partial_write_reports_metadata_commit_without_rollback(publication, capsys):
    context, _, _, git = publication
    git.side_effect = ["", subprocess.CalledProcessError(1, ["git", "push"])]
    with pytest.raises(subprocess.CalledProcessError):
        curation_actions.publish(context)
    assert git.call_count == 2
    assert "--force-with-lease=refs/heads/metadata-review:" + context["metadata_head"] in git.call_args_list[0].args
    assert "--force-with-lease=refs/heads/automation/curation/1:" + context["head"] in git.call_args_list[1].args
    diagnostic = capsys.readouterr().err
    assert context["metadata_result"] in diagnostic
    assert "Partial write" in diagnostic
    assert "metadata-token" not in diagnostic
    assert "website-token" not in diagnostic


@pytest.mark.parametrize("changed", [None, "body", "author"])
def test_comment_identity_ignores_extra_api_user_fields(tmp_path, monkeypatch, changed):
    import json
    from copy import deepcopy

    submission = {"repository": "example/site", "pull_request": 8,
                  "head_sha": "a" * 40, "proposal_sha": "b" * 40,
                  "adapter": "fixture"}
    comment = {"id": 7, "body": "/curation submit\n```json\n" + json.dumps(submission) + "\n```",
               "user": {"id": 1, "login": "curator", "type": "User"},
               "created_at": "now", "updated_at": "now", "html_url": "https://github.com/comment/7"}
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"comment": comment, "issue": {"number": 8}}))
    current = deepcopy(comment)
    current["user"]["user_view_type"] = "public"
    if changed == "body":
        current["body"] += "changed"
    if changed == "author":
        current["user"]["id"] = 2
    pull = {"state": "open", "draft": True,
            "head": {"sha": "a" * 40, "ref": "review", "repo": {"full_name": "example/site"}},
            "base": {"sha": "c" * 40}}
    monkeypatch.setattr(curation_actions, "api", Mock(side_effect=[current, pull]))
    monkeypatch.setattr(curation_actions, "git", Mock(return_value="c" * 40))
    monkeypatch.setattr(curation_actions, "_site_gitlink", Mock(return_value="d" * 40))
    monkeypatch.setattr(curation_actions, "SCRATCH", tmp_path / "scratch")
    monkeypatch.setattr(curation_actions, "CONTEXT", tmp_path / "scratch/context.json")
    for key, value in {"GITHUB_EVENT_PATH": str(event), "GITHUB_EVENT_NAME": "issue_comment",
                       "GITHUB_REPOSITORY": "example/site", "GITHUB_RUN_ID": "1",
                       "GITHUB_OUTPUT": str(tmp_path / "output")}.items():
        monkeypatch.setenv(key, value)
    if changed:
        with pytest.raises(RuntimeError, match="comment.*changed"):
            curation_actions.prepare()
    else:
        curation_actions.prepare()
        assert json.loads(curation_actions.CONTEXT.read_text())["comment_id"] == 7


@pytest.fixture
def coordinated_run(tmp_path, monkeypatch):
    import json
    context = {"repository": "example/site", "head": "a" * 40, "comment_id": None,
               "has_changes": True, "result": "b" * 40}
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context))
    monkeypatch.setattr(curation_actions, "CONTEXT", context_path)
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"repository": {"default_branch": "main"}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    monkeypatch.setenv("GH_TOKEN", "builtin-read")
    credentials = {"token": "metadata-secret", "website_token": "website-secret",
                   "repository": "example/metadata", "head": "c" * 40}
    monkeypatch.setattr(curation_actions, "access", Mock(return_value=credentials))
    monkeypatch.setattr(curation_actions, "revoke", Mock())
    return context, tmp_path


def test_validation_releases_read_access_before_running_adapter(coordinated_run, monkeypatch):
    import os
    monkeypatch.setattr(curation_actions, "prepare", Mock())
    def checkout(context):
        assert os.environ["METADATA_TOKEN"] == "metadata-secret"
    def record(context):
        assert "METADATA_TOKEN" not in os.environ
        curation_actions.revoke.assert_called_once_with("metadata-secret")
        raise RuntimeError("invalid graph")
    monkeypatch.setattr(curation_actions, "checkout", checkout)
    monkeypatch.setattr(curation_actions, "record", record)
    with pytest.raises(RuntimeError, match="invalid graph"):
        curation_actions.validate_run()
    assert curation_actions.access.call_args.kwargs == {}


def test_failed_checkout_releases_read_access(coordinated_run, monkeypatch):
    import os
    monkeypatch.setattr(curation_actions, "prepare", Mock())
    monkeypatch.setattr(curation_actions, "checkout", Mock(side_effect=RuntimeError("checkout failed")))
    with pytest.raises(RuntimeError, match="checkout failed"):
        curation_actions.validate_run()
    curation_actions.revoke.assert_called_once_with("metadata-secret")
    assert "METADATA_TOKEN" not in os.environ


def test_failed_publication_attempts_both_revocations(coordinated_run, monkeypatch):
    import os
    monkeypatch.setattr(curation_actions, "publish", Mock(side_effect=RuntimeError("push failed")))
    curation_actions.revoke.side_effect = [RuntimeError("revocation failed"), None]
    with pytest.raises(RuntimeError, match="revocation failed"):
        curation_actions.publish_run()
    assert [call.args[0] for call in curation_actions.revoke.call_args_list] == ["metadata-secret", "website-secret"]
    assert os.environ["GH_TOKEN"] == "builtin-read"
    assert "METADATA_TOKEN" not in os.environ


def test_proposal_retains_only_review_access_until_artifact_completion(coordinated_run, monkeypatch):
    import os
    _, root = coordinated_run
    monkeypatch.setattr(curation_actions, "publish", Mock())
    monkeypatch.setattr(curation_actions, "bundle", Mock())
    curation_actions.publish_run()
    curation_actions.revoke.assert_called_once_with("metadata-secret")
    assert "metadata-secret" not in (root / "output").read_text()
    assert "review_token=website-secret" in (root / "output").read_text()
    assert "secret" not in (root / "context.json").read_text()
    assert os.environ["GH_TOKEN"] == "builtin-read"
    monkeypatch.setenv("CURATION_REVIEW_TOKEN", "website-secret")
    def announce(context):
        assert os.environ["ARTIFACT_ID"] == "123"
        assert os.environ["GH_TOKEN"] == "website-secret"
    monkeypatch.setattr(curation_actions, "announce", announce)
    curation_actions.complete_run("123")
    assert curation_actions.revoke.call_args.args == ("website-secret",)
    assert os.environ["GH_TOKEN"] == "builtin-read"


@pytest.mark.parametrize("artifact", ["", "123"])
def test_completion_revokes_access_after_missing_upload_or_failed_comment(monkeypatch, coordinated_run, artifact):
    monkeypatch.setenv("CURATION_REVIEW_TOKEN", "website-secret")
    monkeypatch.setattr(curation_actions, "announce", Mock(side_effect=RuntimeError("comment failed")))
    if artifact:
        with pytest.raises(RuntimeError, match="comment failed"):
            curation_actions.complete_run(artifact)
    else:
        curation_actions.complete_run(artifact)
        curation_actions.announce.assert_not_called()
    curation_actions.revoke.assert_called_once_with("website-secret")


def test_no_candidates_requests_no_write_access(coordinated_run):
    import json
    context, _ = coordinated_run
    context["has_changes"] = False
    curation_actions.CONTEXT.write_text(json.dumps(context))
    curation_actions.publish_run()
    curation_actions.access.assert_not_called()


def test_finalization_completes_without_exporting_credentials(coordinated_run, monkeypatch):
    import json
    context, root = coordinated_run
    context["comment_id"] = 7
    curation_actions.CONTEXT.write_text(json.dumps(context))
    monkeypatch.setattr(curation_actions, "publish", Mock())
    monkeypatch.setattr(curation_actions, "announce", Mock())
    monkeypatch.setattr(curation_actions, "bundle", Mock())
    curation_actions.publish_run()
    curation_actions.announce.assert_called_once()
    curation_actions.bundle.assert_not_called()
    assert not (root / "output").exists()
    assert {call.args[0] for call in curation_actions.revoke.call_args_list} == {"metadata-secret", "website-secret"}

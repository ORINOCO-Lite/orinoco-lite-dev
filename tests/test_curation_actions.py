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

"""Transport boundaries for a trusted Actions job's installation access."""
from unittest.mock import patch
import urllib.error

import pytest

from orinoco_lite import workflow_access


@pytest.mark.parametrize("configured", [True, False])
def test_workflow_access_without_metadata_uses_exact_service_audience_and_masks_credentials(tmp_path, monkeypatch, capsys, configured):
    output = tmp_path / "output"
    monkeypatch.chdir(tmp_path)
    (tmp_path / "orinoco.yaml").write_text(
        "contract_version: 2\n" + ("site:\n  curation_service: https://review.example\n" if configured else "")
    )
    origin = "https://review.example" if configured else workflow_access.DEFAULT_CURATION_SERVICE
    for key, value in {
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.actions.githubusercontent.com/token?api-version=2",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-secret",
        "GITHUB_REPOSITORY": "example/site",
        "PROPOSAL_NUMBER": "7",
        "PROPOSAL_HEAD": "a" * 40,
        "GITHUB_OUTPUT": str(output),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("sys.argv", ["workflow-access", "--write"])
    with patch.object(
        workflow_access, "request_json", side_effect=[{"value": "oidc-secret"}, {"token": "installation-secret"}]
    ) as request:
        workflow_access.main()
    assert "audience=" + workflow_access.urllib.parse.quote(f"{origin}/api/shacl/workflow-access", safe="") in request.call_args_list[0].args[0]
    assert request.call_args_list[1].args == (
        f"{origin}/api/shacl/workflow-access", "oidc-secret",
        {"repository": "example/site", "pull_request": 7, "head": "a" * 40, "write": True},
    )
    assert capsys.readouterr().out == "::add-mask::oidc-secret\n::add-mask::installation-secret\n"
    assert output.read_text() == "token=installation-secret\n"


def test_credentials_cannot_follow_redirects():
    with pytest.raises(RuntimeError, match="must not redirect"):
        workflow_access.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://attacker.example")


def test_transport_failure_does_not_print_credentials_or_untrusted_body():
    with patch("urllib.request.OpenerDirector.open", side_effect=urllib.error.HTTPError(
        "https://review.example", 403, "untrusted response", {}, None
    )) as opened:
        with pytest.raises(RuntimeError, match="HTTP 403") as caught:
            workflow_access.request_json("https://review.example", "secret")
    assert opened.call_args.args[0].get_header("User-agent") == "orinoco-lite-workflow-access"
    assert "secret" not in str(caught.value)
    assert "untrusted response" not in str(caught.value)


def test_curation_write_access_masks_both_repository_tokens(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "orinoco.yaml").write_text("contract_version: 2\n")
    output = tmp_path / "output"
    for key, value in {
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.actions.githubusercontent.com/token?api-version=2",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-secret",
        "GITHUB_REPOSITORY": "example/site", "PROPOSAL_NUMBER": "7",
        "PROPOSAL_HEAD": "a" * 40, "CURATION_COMMENT_ID": "9",
        "GITHUB_OUTPUT": str(output),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("sys.argv", ["workflow-access", "--curation", "--write"])
    with patch.object(workflow_access, "request_json", side_effect=[
        {"value": "oidc-secret"},
        {"token": "metadata-secret", "website_token": "website-secret",
         "repository": "example/metadata", "head": "b" * 40},
    ]) as request:
        workflow_access.main()
    assert request.call_args_list[1].args[0].endswith("/api/curation/workflow-access")
    assert request.call_args_list[1].args[2] == {
        "repository": "example/site", "head": "a" * 40,
        "comment_id": 9, "write": True,
    }
    assert capsys.readouterr().out == (
        "::add-mask::oidc-secret\n::add-mask::metadata-secret\n::add-mask::website-secret\n"
    )
    assert "website_token=website-secret\n" in output.read_text()

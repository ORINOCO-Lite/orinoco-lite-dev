"""Transport boundaries for a trusted Actions job's installation access."""
from unittest.mock import patch
import urllib.error

import pytest

from orinoco_lite import workflow_access


@pytest.mark.parametrize("configured", [True, False])
def test_workflow_access_without_metadata_uses_exact_service_audience_and_masks_credentials(tmp_path, monkeypatch, capsys, configured):
    output = tmp_path / "output"
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.orinoco]\n" + ("[tool.orinoco.service]\nurl = 'https://review.example'\n" if configured else "")
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
    (tmp_path / "pyproject.toml").write_text("[tool.orinoco]\n")
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


def test_template_access_uses_dispatch_base_without_proposal(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.orinoco]\n")
    output = tmp_path / "output"
    for key, value in {
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.actions.githubusercontent.com/token?api-version=2",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-secret",
        "GITHUB_REPOSITORY": "example/site", "GITHUB_SHA": "a" * 40,
        "GITHUB_OUTPUT": str(output),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PROPOSAL_HEAD", raising=False)
    monkeypatch.delenv("PROPOSAL_NUMBER", raising=False)
    monkeypatch.setattr("sys.argv", ["workflow-access", "--template"])
    with patch.object(workflow_access, "request_json", side_effect=[
        {"value": "oidc-secret"}, {"token": "bot-secret"},
    ]) as request:
        workflow_access.main()
    assert request.call_args_list[1].args[0].endswith("/api/template/workflow-access")
    assert request.call_args_list[1].args[2] == {"repository": "example/site", "head": "a" * 40}
    assert capsys.readouterr().out == "::add-mask::oidc-secret\n::add-mask::bot-secret\n"
    assert output.read_text() == "token=bot-secret\n"


@pytest.mark.parametrize("enabled", [True, False])
def test_workflow_token_transport_checks_current_default_branch(enabled):
    import base64
    policy = f"[tool.orinoco]\n[tool.orinoco.operations]\nshacl_materialization = {str(enabled).lower()}\n"
    with patch.object(workflow_access, "request_json", side_effect=[
        {"default_branch": "main"}, {"commit": {"sha": "a" * 40}},
        {"content": base64.b64encode(policy.encode()).decode()},
    ]) as request:
        if enabled:
            workflow_access.require_operation("owner/site", "shacl_materialization", "secret")
        else:
            with pytest.raises(workflow_access.ConfigurationError, match="Enable tool.orinoco.operations.shacl_materialization"):
                workflow_access.require_operation("owner/site", "shacl_materialization", "secret")
    assert request.call_args_list[1].args[0].endswith("/branches/main")
    assert request.call_args_list[2].args[0].endswith("/contents/pyproject.toml?ref=" + "a" * 40)


def test_template_child_access_masks_token_and_validates_coordinates(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.orinoco]\n")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://example.actions.githubusercontent.com/token?api-version=2")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-secret")
    result = {"token": "parent-secret", "site_token": "child-secret",
              "site_repository": "owner/inputs", "site_head": "a" * 40, "site_branch": "main"}
    body = {"repository": "owner/site", "head": "b" * 40, "site_specific": True}
    with patch.object(workflow_access, "request_json", side_effect=[{"value": "identity-secret"}, result]):
        assert workflow_access.obtain(body, template=True) == result
    assert "::add-mask::child-secret" in capsys.readouterr().out
    for key, value in [("site_token", "bad\nvalue"), ("site_repository", "owner/inputs\nextra"),
                       ("site_head", "main"), ("site_branch", "main\nextra")]:
        with patch.object(workflow_access, "request_json", side_effect=[{"value": "identity-secret"}, {**result, key: value}]):
            with pytest.raises(RuntimeError):
                workflow_access.obtain(body, template=True)

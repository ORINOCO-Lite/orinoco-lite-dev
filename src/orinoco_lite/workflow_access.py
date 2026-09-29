"""Obtain bounded curation-App access for a trusted GitHub Actions job.

No credential is retained in the checkout. GitHub masks the short-lived result;
only the explicitly selected transport step receives the output token.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from .config import DEFAULT_CURATION_SERVICE, _curation_service_origin, read_configuration, parse_configuration, validate_operations
from .errors import ConfigurationError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Credential-bearing requests must not redirect")


def request_json(url: str, token: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "orinoco-lite-workflow-access",
        },
        data=None if body is None else json.dumps(body).encode(),
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        # Do not print response bodies, request headers, or identity tokens.
        raise RuntimeError(f"Workflow authorization was rejected (HTTP {error.code}); inspect the draft and service configuration") from None
    if not isinstance(result, dict):
        raise RuntimeError("Workflow authorization returned invalid JSON")
    return result


def obtain(body: dict, *, curation: bool = False, template: bool = False) -> dict:
    """Request and mask installation credentials without exporting them to Actions."""
    # Metadata may be a private, not-yet-initialized submodule. Only the
    # trusted website configuration is needed to obtain its checkout token.
    raw = read_configuration(Path.cwd() / "pyproject.toml")
    service = raw.get("service", {})
    if not isinstance(service, dict):
        raise ConfigurationError("tool.orinoco.service must be a table")
    origin = _curation_service_origin(
        service.get("url", DEFAULT_CURATION_SERVICE), "tool.orinoco.service.url")
    operation = "template" if template else "curation" if curation else "shacl"
    endpoint = f"{origin}/api/{operation}/workflow-access"
    identity_url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    parsed = urllib.parse.urlsplit(identity_url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".actions.githubusercontent.com"):
        raise RuntimeError("Unexpected GitHub Actions identity endpoint")
    identity = request_json(
        identity_url + "&audience=" + urllib.parse.quote(endpoint, safe=""),
        os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"],
    ).get("value")
    if not isinstance(identity, str) or not identity or "\n" in identity:
        raise RuntimeError("GitHub did not return an Actions identity")
    print(f"::add-mask::{identity}")
    result = request_json(endpoint, identity, body)
    token = result.get("token")
    if not isinstance(token, str) or not token or any(c in token for c in "\r\n\0"):
        raise RuntimeError("The service did not return bounded access")
    print(f"::add-mask::{token}")
    if curation and body["write"]:
        website_token = result.get("website_token")
        if not isinstance(website_token, str) or not website_token or any(c in website_token for c in "\r\n\0"):
            raise RuntimeError("The service did not return bounded website access")
        print(f"::add-mask::{website_token}")
    if template and body.get("site_specific"):
        site_token = result.get("site_token")
        if not isinstance(site_token, str) or not site_token or any(c in site_token for c in "\r\n\0"):
            raise RuntimeError("The service did not return site-specific access")
        print(f"::add-mask::{site_token}")
        for key, pattern in (("site_repository", r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"),
                             ("site_head", r"[0-9a-f]{40}"), ("site_branch", r"[^\s\x00-\x1f]+")):
            if not isinstance(result.get(key), str) or not re.fullmatch(pattern, result[key]):
                raise RuntimeError("Invalid site-specific checkout coordinate")
    if curation:
        for key in ("repository", "head"):
            value = result.get(key)
            if not isinstance(value, str) or any(c in value for c in "\r\n\0"):
                raise RuntimeError("Invalid metadata checkout coordinate")
    return result


def revoke(token: str) -> None:
    """Revoke an installation token without exposing it to a subprocess."""
    request = urllib.request.Request(
        "https://api.github.com/installation/token", method="DELETE",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "orinoco-lite-workflow-access"},
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30):
            pass
    except urllib.error.HTTPError as error:
        if error.code != 401:  # Already expired or revoked.
            raise RuntimeError(f"Installation token revocation failed (HTTP {error.code})") from None


def require_operation(repository: str, operation: str, token: str) -> None:
    """Check current default-branch policy for transport using a workflow token."""
    validate_operations({operation: True})
    api = f"https://api.github.com/repos/{repository}"
    repo = request_json(api, token)
    branch = urllib.parse.quote(repo["default_branch"], safe="")
    head = request_json(f"{api}/branches/{branch}", token)["commit"]["sha"]
    content = request_json(f"{api}/contents/pyproject.toml?ref={head}", token)
    config = parse_configuration(base64.b64decode(content["content"]).decode("utf-8"))
    if validate_operations(config.get("operations", {})).get(operation) is not True:
        raise ConfigurationError(f"Enable tool.orinoco.operations.{operation} in pyproject.toml on the repository default branch before using this operation")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--curation", action="store_true")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--site-specific", action="store_true")
    parser.add_argument("--check-operation")
    args = parser.parse_args()
    if args.site_specific and not args.template:
        parser.error("--site-specific requires --template")
    if args.check_operation:
        require_operation(os.environ["GITHUB_REPOSITORY"], args.check_operation, os.environ["GH_TOKEN"])
        return
    body = {
        "repository": os.environ["GITHUB_REPOSITORY"],
        "pull_request": int(os.environ.get("PROPOSAL_NUMBER", "0")),
        "head": os.environ["GITHUB_SHA"] if args.template else os.environ["PROPOSAL_HEAD"],
        "write": args.write,
    }
    if args.curation:
        body.pop("pull_request")
        body["comment_id"] = int(os.environ["CURATION_COMMENT_ID"]) if os.environ.get("CURATION_COMMENT_ID") else None
    if args.template:
        body = {"repository": os.environ["GITHUB_REPOSITORY"], "head": os.environ["GITHUB_SHA"]}
        if args.site_specific:
            body["site_specific"] = True
    if os.environ.get("PROPOSAL_HANDOFF") and not args.curation:
        body["handoff"] = os.environ["PROPOSAL_HANDOFF"]
    result = obtain(body, curation=args.curation, template=args.template)
    keys = ["token"]
    if args.site_specific:
        keys += ["site_token", "site_repository", "site_head", "site_branch"]
    if args.curation:
        keys += ["repository", "head"]
        if args.write:
            keys.append("website_token")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        for key in keys:
            output.write(f"{key}={result[key]}\n")


if __name__ == "__main__":
    main()

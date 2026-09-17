"""Obtain bounded curation-App access for a trusted GitHub Actions job.

No credential is retained in the checkout. GitHub masks the short-lived result;
only the explicitly selected transport step receives the output token.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from .config import DEFAULT_CURATION_SERVICE, _curation_service_origin, _load_mapping
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


def obtain(body: dict, *, curation: bool = False) -> dict:
    """Request and mask installation credentials without exporting them to Actions."""
    # Metadata may be a private, not-yet-initialized submodule. Only the
    # trusted website configuration is needed to obtain its checkout token.
    raw = _load_mapping(Path.cwd() / "orinoco.yaml", "Workspace configuration")
    site = raw.get("site", {})
    if not isinstance(site, dict):
        raise ConfigurationError("orinoco.yaml site must be a mapping")
    service = site.get("curation_service")
    origin = _curation_service_origin(
        DEFAULT_CURATION_SERVICE if service is None else service,
        "orinoco.yaml site.curation_service",
    )
    endpoint = f"{origin}/api/{"curation" if curation else "shacl"}/workflow-access"
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--curation", action="store_true")
    args = parser.parse_args()
    body = {
        "repository": os.environ["GITHUB_REPOSITORY"],
        "pull_request": int(os.environ["PROPOSAL_NUMBER"]),
        "head": os.environ["PROPOSAL_HEAD"],
        "write": args.write,
    }
    if args.curation:
        body.pop("pull_request")
        body["comment_id"] = int(os.environ["CURATION_COMMENT_ID"]) if os.environ.get("CURATION_COMMENT_ID") else None
    if os.environ.get("PROPOSAL_HANDOFF") and not args.curation:
        body["handoff"] = os.environ["PROPOSAL_HANDOFF"]
    result = obtain(body, curation=args.curation)
    keys = ["token"]
    if args.curation:
        keys += ["repository", "head"]
        if args.write:
            keys.append("website_token")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        for key in keys:
            output.write(f"{key}={result[key]}\n")


if __name__ == "__main__":
    main()

import { authenticatedRequest } from "../../lib/authenticated-request";
import {
  browserCredentialScope,
  issueBrowserCredentials,
} from "../../lib/browser-access";
import { GitHubClient } from "../../lib/github";
import {
  HttpError,
  jsonResponse,
  readJsonBody,
  requireExactKeys,
} from "../../lib/http";
import type { EventContext } from "../../lib/pages";

export async function onRequest(context: EventContext): Promise<Response> {
  const session = await authenticatedRequest(context);
  const input = await readJsonBody(context.request, 4096);
  requireExactKeys(input, ["kind", "source_commit"], "credential request");
  const grant =
    input.kind === "shacl"
      ? session.shacl_grant
      : input.kind === "review"
        ? session.review_grant
        : null;
  if (grant === null || typeof input.source_commit !== "string")
    throw new HttpError(
      403,
      "authentication_required",
      "Sign in from the downstream website to request credentials.",
    );
  const origin =
    "editor_origin" in grant ? grant.editor_origin : grant.review_origin;
  const scope = await browserCredentialScope(
    context.env,
    new GitHubClient(session.access_token),
    grant.repository,
    origin,
    input.source_commit,
  );
  return jsonResponse(
    await issueBrowserCredentials(
      context.env,
      session.access_token,
      scope,
      session.expires_at,
    ),
  );
}

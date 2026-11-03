import { authenticatedRequest } from "../../lib/authenticated-request";
import { verifyBrowserCredentialScope } from "../../lib/browser-access";
import { GitHubClient } from "../../lib/github";
import {
  HttpError,
  jsonResponse,
  readJsonBody,
  requireExactKeys,
} from "../../lib/http";
import type { EventContext } from "../../lib/pages";
import { authorizeSubmission } from "../../lib/workflow-authorization";

export async function onRequest(context: EventContext): Promise<Response> {
  const session = await authenticatedRequest(context);
  const input = await readJsonBody(context.request, 16384);
  requireExactKeys(
    input,
    ["scope_proof", "input_repository", "input_commit"],
    "submission authorization",
  );
  if (
    typeof input.scope_proof !== "string" ||
    typeof input.input_repository !== "string" ||
    typeof input.input_commit !== "string"
  )
    throw new HttpError(
      400,
      "invalid_payload",
      "The submission authorization coordinates are invalid.",
    );
  const scope = await verifyBrowserCredentialScope(
    context.env,
    session.access_token,
    input.scope_proof,
  );
  const authorization = await authorizeSubmission(
    context.env,
    new GitHubClient(session.access_token),
    {
      scope,
      input_repository: input.input_repository,
      input_commit: input.input_commit,
    },
  );
  return jsonResponse({ authorization });
}

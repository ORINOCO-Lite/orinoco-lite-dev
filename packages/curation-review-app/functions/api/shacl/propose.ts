import { equalTokens } from "../../lib/encoding";
import { GitHubClient } from "../../lib/github";
import {
  HttpError,
  jsonResponse,
  readJsonBody,
  requireJsonContentType,
  requireMethod,
  requireSameOrigin,
} from "../../lib/http";
import type { EventContext } from "../../lib/pages";
import {
  MAX_SHACL_PROPOSAL_BODY_BYTES,
  parseShaclProposalRequest,
} from "../../lib/shacl";
import { createShaclProposal } from "../../lib/shacl-proposal";
import { configuredOrigin, readSessionCookie } from "../../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  requireSameOrigin(context.request, configuredOrigin(context.env));
  const url = new URL(context.request.url);
  if ([...url.searchParams.keys()].length > 0) {
    throw new HttpError(
      400,
      "unexpected_query",
      "The SHACL proposal endpoint does not accept query fields.",
    );
  }
  const session = await readSessionCookie(context.request, context.env);
  const supplied = context.request.headers.get("x-csrf-token") ?? "";
  if (!equalTokens(supplied, session.csrf_token)) {
    throw new HttpError(403, "invalid_csrf", "The request token is invalid.");
  }
  const proposal = parseShaclProposalRequest(
    await readJsonBody(context.request, MAX_SHACL_PROPOSAL_BODY_BYTES),
  );
  const result = await createShaclProposal(
    new GitHubClient(session.access_token),
    proposal,
  );
  return jsonResponse(result, { status: 201 });
}

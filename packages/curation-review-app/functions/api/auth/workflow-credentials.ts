import {
  jsonResponse,
  readJsonBody,
  requireExactKeys,
  requireJsonContentType,
  requireMethod,
  HttpError,
} from "../../lib/http";
import type { EventContext } from "../../lib/pages";
import { verifyWorkflowIdentity } from "../../lib/workflow-access";
import { submissionCredentials } from "../../lib/workflow-authorization";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  const identity = await verifyWorkflowIdentity(
    context.request.headers.get("authorization")?.replace(/^Bearer /, "") ?? "",
    context.env.PUBLIC_ORIGIN,
    undefined,
    "/api/auth/workflow-credentials",
  );
  const input = await readJsonBody(context.request, 16384);
  requireExactKeys(input, ["authorization"], "workflow credential request");
  if (typeof input.authorization !== "string")
    throw new HttpError(
      400,
      "invalid_payload",
      "The submission authorization is required.",
    );
  return jsonResponse(
    await submissionCredentials(context.env, input.authorization, identity),
  );
}

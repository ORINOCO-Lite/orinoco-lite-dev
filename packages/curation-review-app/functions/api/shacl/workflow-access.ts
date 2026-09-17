import type { EventContext } from "../../lib/pages";
import {
  HttpError,
  jsonResponse,
  readJsonBody,
  requireMethod,
  requireJsonContentType,
} from "../../lib/http";
import {
  object,
  verifyWorkflowIdentity,
  workflowAccess,
} from "../../lib/workflow-access";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  const identity = await verifyWorkflowIdentity(
    context.request.headers.get("authorization")?.replace(/^Bearer /, "") ?? "",
    context.env.PUBLIC_ORIGIN,
  );
  try {
    return jsonResponse(
      await workflowAccess(
        context.env,
        identity,
        object(await readJsonBody(context.request, 4096)),
      ),
    );
  } catch (error) {
    if (error instanceof HttpError)
      console.warn("Workflow access error:", error.code);
    throw error;
  }
}

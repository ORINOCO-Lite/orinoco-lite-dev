import type { EventContext } from "../../lib/pages";
import {
  jsonResponse,
  readJsonBody,
  requireMethod,
  requireJsonContentType,
} from "../../lib/http";
import { object, verifyWorkflowIdentity } from "../../lib/workflow-access";
import { templateWorkflowAccess } from "../../lib/template-workflow";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  const identity = await verifyWorkflowIdentity(
    context.request.headers.get("authorization")?.replace(/^Bearer /, "") ?? "",
    context.env.PUBLIC_ORIGIN,
    undefined,
    "/api/template/workflow-access",
  );
  return jsonResponse(
    await templateWorkflowAccess(
      context.env,
      identity,
      object(await readJsonBody(context.request, 4096)),
    ),
  );
}

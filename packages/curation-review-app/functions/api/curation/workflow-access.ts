import type { EventContext } from "../../lib/pages";
import {
  jsonResponse,
  readJsonBody,
  requireMethod,
  requireJsonContentType,
} from "../../lib/http";
import { object, verifyWorkflowIdentity } from "../../lib/workflow-access";
import { curationWorkflowAccess } from "../../lib/curation-workflow";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  const identity = await verifyWorkflowIdentity(
    context.request.headers.get("authorization")?.replace(/^Bearer /, "") ?? "",
    context.env.PUBLIC_ORIGIN,
    undefined,
    "/api/curation/workflow-access",
  );
  return jsonResponse(
    await curationWorkflowAccess(
      context.env,
      identity,
      object(await readJsonBody(context.request, 4096)),
    ),
  );
}

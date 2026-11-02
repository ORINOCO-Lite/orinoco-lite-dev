import type { EventContext } from "../../lib/pages";
import {
  jsonResponse,
  readJsonBody,
  requireMethod,
  requireJsonContentType,
} from "../../lib/http";
import { metadataReadAccess } from "../../lib/metadata-read";
import { object, verifyWorkflowIdentity } from "../../lib/workflow-access";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  const identity = await verifyWorkflowIdentity(
    context.request.headers.get("authorization")?.replace(/^Bearer /, "") ?? "",
    context.env.PUBLIC_ORIGIN,
    undefined,
    "/api/shacl/metadata-access",
  );
  return jsonResponse(
    await metadataReadAccess(
      context.env,
      identity,
      object(await readJsonBody(context.request, 4096)),
    ),
  );
}

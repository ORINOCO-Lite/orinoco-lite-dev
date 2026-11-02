import { authenticatedRequest } from "../../lib/authenticated-request";
import { HttpError, readJsonBody, requireExactKeys } from "../../lib/http";
import type { EventContext } from "../../lib/pages";
import { revokeUserCredential } from "../../lib/user-credentials";

export async function onRequest(context: EventContext): Promise<Response> {
  await authenticatedRequest(context);
  const input = await readJsonBody(context.request, 4096);
  requireExactKeys(input, ["token"], "credential revocation");
  if (
    typeof input.token !== "string" ||
    !input.token ||
    input.token.length > 1024 ||
    /\s/.test(input.token)
  )
    throw new HttpError(
      400,
      "invalid_payload",
      "The repository credential is invalid.",
    );
  await revokeUserCredential(context.env, input.token);
  return new Response(null, { status: 204 });
}

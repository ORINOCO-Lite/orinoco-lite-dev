import { errorResponse, withApiHeaders } from "../lib/http";
import type { EventContext } from "../lib/pages";

export async function onRequest(context: EventContext): Promise<Response> {
  try {
    return withApiHeaders(await context.next());
  } catch (error) {
    return errorResponse(error);
  }
}

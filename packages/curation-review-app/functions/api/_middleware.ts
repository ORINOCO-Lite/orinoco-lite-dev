import { errorResponse, HttpError, withApiHeaders } from "../lib/http";
import type { EventContext } from "../lib/pages";

export async function onRequest(context: EventContext): Promise<Response> {
  try {
    return withApiHeaders(await context.next());
  } catch (error) {
    if (!(error instanceof HttpError)) {
      console.error("Unhandled review-service error", error);
    }
    return errorResponse(error);
  }
}

import { errorResponse, HttpError, withApiHeaders } from "../lib/http";
import type { EventContext } from "../lib/pages";

export async function onRequest(context: EventContext): Promise<Response> {
  try {
    const response = await context.next();
    const editorHtml =
      new URL(context.request.url).pathname === "/api/shacl/editor" &&
      response.headers
        .get("content-type")
        ?.toLowerCase()
        .startsWith("text/html");
    return editorHtml ? response : withApiHeaders(response);
  } catch (error) {
    if (!(error instanceof HttpError)) {
      console.error("Unhandled review-service error", error);
    }
    return errorResponse(error);
  }
}

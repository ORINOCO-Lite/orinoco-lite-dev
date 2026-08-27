import { HttpError, requireMethod } from "../lib/http";
import type { EventContext } from "../lib/pages";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  throw new HttpError(
    410,
    "review_discovery_retired",
    "Central review discovery is retired. Open /review/ on the deployed downstream site from its curation workflow link.",
  );
}

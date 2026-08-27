import { withApiHeaders } from "./lib/http";

export function onRequest(): Response {
  return withApiHeaders(new Response(null, { status: 404 }));
}

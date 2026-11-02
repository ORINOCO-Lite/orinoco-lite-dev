import { HttpError, jsonResponse, requireMethod } from "../../lib/http";
import { advanceWebsiteGitlink } from "../../lib/metadata-merge";
import type { EventContext } from "../../lib/pages";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  const secret = context.env.GITHUB_WEBHOOK_SECRET;
  if (!secret)
    throw new HttpError(
      503,
      "webhook_unavailable",
      "The GitHub App webhook is not configured.",
    );
  const signature = context.request.headers.get("x-hub-signature-256") ?? "";
  if (!/^sha256=[0-9a-f]{64}$/.test(signature))
    throw new HttpError(
      401,
      "invalid_signature",
      "Invalid GitHub webhook signature.",
    );
  const bytes = new Uint8Array(await context.request.arrayBuffer());
  if (bytes.length > 1_048_576)
    throw new HttpError(413, "body_too_large", "GitHub webhook is too large.");
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const supplied = Uint8Array.from(signature.slice(7).match(/../g)!, (part) =>
    parseInt(part, 16),
  );
  if (!(await crypto.subtle.verify("HMAC", key, supplied, bytes)))
    throw new HttpError(
      401,
      "invalid_signature",
      "Invalid GitHub webhook signature.",
    );
  if (context.request.headers.get("x-github-event") !== "pull_request")
    return jsonResponse({ updated: false });
  let payload: unknown;
  try {
    payload = JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    throw new HttpError(400, "invalid_json", "Invalid GitHub webhook JSON.");
  }
  return jsonResponse({
    updated: await advanceWebsiteGitlink(context.env, payload),
  });
}

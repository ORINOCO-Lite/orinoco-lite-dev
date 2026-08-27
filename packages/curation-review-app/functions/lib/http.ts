export class HttpError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
  }
}

export const API_SECURITY_HEADERS: Readonly<Record<string, string>> = {
  "Cache-Control": "no-store",
  "Content-Security-Policy":
    "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; sandbox",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Permissions-Policy":
    "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
  Pragma: "no-cache",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
};

export function jsonResponse(
  value: unknown,
  init: ResponseInit = {},
): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json; charset=utf-8");
  for (const [name, headerValue] of Object.entries(API_SECURITY_HEADERS)) {
    headers.set(name, headerValue);
  }
  return new Response(JSON.stringify(value), { ...init, headers });
}

export function errorResponse(error: unknown): Response {
  if (error instanceof HttpError) {
    return jsonResponse(
      { error: { code: error.code, message: error.message } },
      { status: error.status },
    );
  }
  return jsonResponse(
    {
      error: {
        code: "internal_error",
        message: "The review service could not complete the request.",
      },
    },
    { status: 500 },
  );
}

export function withApiHeaders(response: Response): Response {
  const result = new Response(response.body, response);
  for (const [name, value] of Object.entries(API_SECURITY_HEADERS)) {
    if (!result.headers.has(name)) result.headers.set(name, value);
  }
  return result;
}

export function requireMethod(request: Request, method: string): void {
  if (request.method !== method) {
    throw new HttpError(
      405,
      "method_not_allowed",
      `Use ${method} for this endpoint.`,
    );
  }
}

export function requireJsonContentType(request: Request): void {
  const mediaType = request.headers
    .get("content-type")
    ?.split(";", 1)[0]
    ?.trim();
  if (mediaType !== "application/json") {
    throw new HttpError(
      415,
      "unsupported_media_type",
      "The request must use application/json.",
    );
  }
}

export function requireSameOrigin(request: Request, origin: string): void {
  if (request.headers.get("origin") !== origin) {
    throw new HttpError(
      403,
      "invalid_origin",
      "The request origin is not allowed.",
    );
  }
}

export async function readJsonBody(
  request: Request,
  maximumBytes = 262_144,
): Promise<unknown> {
  const contentLength = request.headers.get("content-length");
  if (contentLength !== null) {
    const parsed = Number(contentLength);
    if (!Number.isSafeInteger(parsed) || parsed < 0 || parsed > maximumBytes) {
      throw new HttpError(
        413,
        "body_too_large",
        "The request body is too large.",
      );
    }
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).byteLength > maximumBytes) {
    throw new HttpError(
      413,
      "body_too_large",
      "The request body is too large.",
    );
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new HttpError(
      400,
      "invalid_json",
      "The request body is not valid JSON.",
    );
  }
}

export function requireExactKeys(
  value: unknown,
  expected: readonly string[],
  label: string,
): asserts value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(400, "invalid_payload", `${label} must be an object.`);
  }
  const observed = Object.keys(value).sort();
  const required = [...expected].sort();
  if (
    observed.length !== required.length ||
    observed.some((key, index) => key !== required[index])
  ) {
    throw new HttpError(
      400,
      "invalid_payload",
      `${label} has missing or unexpected fields.`,
    );
  }
}

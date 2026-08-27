import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { withApiHeaders } from "../functions/lib/http";

const ROUTES = resolve("service-dist/_routes.json");

describe("backend-only service output", () => {
  it("routes only API requests to the stateless functions", async () => {
    const routes = JSON.parse(await readFile(ROUTES, "utf8")) as unknown;

    expect(routes).toEqual({ exclude: [], include: ["/api/*"], version: 1 });
  });

  it("preserves the OAuth navigation opener policy through middleware", () => {
    const response = withApiHeaders(
      new Response(null, {
        headers: { "Cross-Origin-Opener-Policy": "unsafe-none" },
        status: 302,
      }),
    );

    expect(response.headers.get("cross-origin-opener-policy")).toBe(
      "unsafe-none",
    );
  });
});

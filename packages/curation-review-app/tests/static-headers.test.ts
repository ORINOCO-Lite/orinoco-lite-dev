import { readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { onRequest as retireRoot } from "../functions/index";
import { API_SECURITY_HEADERS, withApiHeaders } from "../functions/lib/http";

const SERVICE_DIST = resolve("service-dist");
const ROUTES = resolve("service-dist/_routes.json");

describe("backend-only service output", () => {
  it("routes only the root tombstone and API requests to functions", async () => {
    const routes = JSON.parse(await readFile(ROUTES, "utf8")) as unknown;

    expect(routes).toEqual({
      exclude: [],
      include: ["/", "/api/*"],
      version: 1,
    });
  });

  it("contains no static presentation assets", async () => {
    const entries = await readdir(SERVICE_DIST, { withFileTypes: true });

    expect(entries).toHaveLength(1);
    expect(entries[0]?.name).toBe("_routes.json");
    expect(entries[0]?.isFile()).toBe(true);
  });

  it("retires the exact root with an empty hardened 404", async () => {
    const response = retireRoot();

    expect(response.status).toBe(404);
    expect(await response.text()).toBe("");
    expect(response.headers.has("content-type")).toBe(false);
    expect(response.headers.has("location")).toBe(false);
    for (const [name, value] of Object.entries(API_SECURITY_HEADERS)) {
      expect(response.headers.get(name)).toBe(value);
    }
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

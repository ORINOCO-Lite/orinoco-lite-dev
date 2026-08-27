import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const ROUTES = resolve("service-dist/_routes.json");

describe("backend-only service output", () => {
  it("routes only API requests to the stateless functions", async () => {
    const routes = JSON.parse(await readFile(ROUTES, "utf8")) as unknown;

    expect(routes).toEqual({ exclude: [], include: ["/api/*"], version: 1 });
  });
});

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const HEADERS = resolve("public/_headers");

describe("static response headers", () => {
  it("detaches the global no-store directive for fingerprinted assets", async () => {
    const headers = await readFile(HEADERS, "utf8");

    expect(headers).toContain("/*\n  Cache-Control: no-store\n");
    expect(headers).toContain(
      "/assets/*\n" +
        "  ! Cache-Control\n" +
        "  Cache-Control: public, max-age=31536000, immutable\n",
    );
  });
});

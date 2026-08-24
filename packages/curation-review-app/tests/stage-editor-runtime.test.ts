import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import {
  chmod,
  lstat,
  mkdtemp,
  mkdir,
  readFile,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { promisify } from "node:util";
import { afterEach, describe, expect, it } from "vitest";

const execFileAsync = promisify(execFile);
const SCRIPT = resolve("tools/stage-editor-runtime.mjs");
const temporaryRoots: string[] = [];

function sha256(bytes: Uint8Array | string): string {
  return createHash("sha256").update(bytes).digest("hex");
}

async function runtimeFixture(): Promise<{
  manifestSha256: string;
  root: string;
}> {
  const root = await mkdtemp(join(tmpdir(), "orinoco-editor-runtime-"));
  temporaryRoots.push(root);
  const files: Record<string, string> = {
    "editor-schema/config_default_xyzri.yaml": "classes: []\n",
    "editor-schema/dlschemas_owl.ttl": "<urn:owl> a <urn:Schema> .\n",
    "editor-schema/dlschemas_shacl.ttl": "<urn:shacl> a <urn:Schema> .\n",
    "editor-shell/assets/app.js": "globalThis.editorLoaded = true;\n",
    "editor-shell/index.html": '<script src="./assets/app.js"></script>\n',
    "licenses/example.txt": "not staged\n",
  };
  const entries = [];
  for (const [path, content] of Object.entries(files)) {
    const destination = join(root, ...path.split("/"));
    await mkdir(join(destination, ".."), { recursive: true });
    await writeFile(destination, content);
    await chmod(destination, 0o644);
    const bytes = new TextEncoder().encode(content);
    entries.push({
      mode: 0o644,
      path,
      sha256: sha256(bytes),
      size: bytes.length,
    });
  }
  const manifest = `${JSON.stringify({
    files: entries,
    format: "orinoco-lite-runtime",
    manifest_version: 1,
    release: "0.2.0rc1",
  })}\n`;
  await writeFile(join(root, "runtime-manifest.json"), manifest);
  return { manifestSha256: sha256(manifest), root };
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map((path) => rm(path, { force: true, recursive: true })),
  );
});

describe("immutable editor runtime staging", () => {
  it("copies only manifest-verified generic shell and schema files", async () => {
    const fixture = await runtimeFixture();
    const outputRoot = await mkdtemp(join(tmpdir(), "orinoco-editor-output-"));
    temporaryRoots.push(outputRoot);
    const destination = join(outputRoot, "dist", "editor");

    const { stdout } = await execFileAsync(process.execPath, [
      SCRIPT,
      fixture.root,
      fixture.manifestSha256,
      destination,
    ]);

    expect(JSON.parse(stdout)).toMatchObject({
      files: 5,
      manifest_sha256: fixture.manifestSha256,
      release: "0.2.0rc1",
    });
    await expect(
      readFile(join(destination, "index.html"), "utf8"),
    ).resolves.toContain("assets/app.js");
    await expect(
      readFile(join(destination, "dlschemas_shacl.ttl"), "utf8"),
    ).resolves.toContain("urn:shacl");
    await expect(lstat(join(destination, "licenses"))).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  it("rejects the wrong manifest coordinate and modified runtime content", async () => {
    const fixture = await runtimeFixture();
    const outputRoot = await mkdtemp(join(tmpdir(), "orinoco-editor-output-"));
    temporaryRoots.push(outputRoot);

    await expect(
      execFileAsync(process.execPath, [
        SCRIPT,
        fixture.root,
        "f".repeat(64),
        join(outputRoot, "wrong-manifest"),
      ]),
    ).rejects.toMatchObject({
      stderr: expect.stringContaining("does not match"),
    });

    await writeFile(
      join(fixture.root, "editor-shell", "index.html"),
      "modified\n",
    );
    await expect(
      execFileAsync(process.execPath, [
        SCRIPT,
        fixture.root,
        fixture.manifestSha256,
        join(outputRoot, "modified-runtime"),
      ]),
    ).rejects.toMatchObject({ stderr: expect.stringContaining("wrong size") });
  });

  it("rejects symlinked runtime resources", async () => {
    const fixture = await runtimeFixture();
    const outputRoot = await mkdtemp(join(tmpdir(), "orinoco-editor-output-"));
    temporaryRoots.push(outputRoot);
    const index = join(fixture.root, "editor-shell", "index.html");
    await rm(index);
    await symlink(join(fixture.root, "licenses", "example.txt"), index);

    await expect(
      execFileAsync(process.execPath, [
        SCRIPT,
        fixture.root,
        fixture.manifestSha256,
        join(outputRoot, "symlinked-runtime"),
      ]),
    ).rejects.toMatchObject({
      stderr: expect.stringContaining("cannot be a symlink"),
    });
  });
});

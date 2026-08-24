#!/usr/bin/env node

import { createHash } from "node:crypto";
import {
  chmod,
  copyFile,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
} from "node:fs/promises";
import { basename, dirname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const DIGEST = /^[0-9a-f]{64}$/;
const MANIFEST_LIMIT = 16 * 1024 * 1024;
const SCHEMA_FILES = new Set([
  "editor-schema/config_default_xyzri.yaml",
  "editor-schema/dlschemas_owl.ttl",
  "editor-schema/dlschemas_shacl.ttl",
]);

function digest(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function safeManifestPath(value) {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    !value.startsWith("/") &&
    !value.includes("\\") &&
    value.split("/").every((part) => part && part !== "." && part !== "..")
  );
}

async function regularFile(root, relative) {
  let current = root;
  for (const part of relative.split("/")) {
    current = join(current, part);
    const status = await lstat(current);
    if (status.isSymbolicLink()) {
      throw new Error(`Runtime resource cannot be a symlink: ${relative}`);
    }
  }
  const status = await lstat(current);
  if (!status.isFile()) {
    throw new Error(`Runtime resource is not a regular file: ${relative}`);
  }
  return { path: current, status };
}

function targetPath(relative) {
  if (relative.startsWith("editor-shell/")) {
    return relative.slice("editor-shell/".length);
  }
  if (SCHEMA_FILES.has(relative)) return basename(relative);
  return null;
}

export async function stageEditorRuntime({
  destination,
  expectedManifestSha256,
  runtime,
}) {
  if (!DIGEST.test(expectedManifestSha256)) {
    throw new Error(
      "Expected runtime manifest SHA-256 must be lowercase hexadecimal",
    );
  }
  const runtimeRoot = resolve(runtime);
  const runtimeStatus = await lstat(runtimeRoot);
  if (!runtimeStatus.isDirectory() || runtimeStatus.isSymbolicLink()) {
    throw new Error("Runtime root must be a real directory");
  }
  const manifestFile = await regularFile(runtimeRoot, "runtime-manifest.json");
  if (manifestFile.status.size > MANIFEST_LIMIT) {
    throw new Error("Runtime manifest is too large");
  }
  const manifestBytes = await readFile(manifestFile.path);
  if (digest(manifestBytes) !== expectedManifestSha256) {
    throw new Error("Runtime manifest does not match the expected SHA-256");
  }
  let manifest;
  try {
    manifest = JSON.parse(manifestBytes.toString("utf8"));
  } catch {
    throw new Error("Runtime manifest is not valid JSON");
  }
  if (
    manifest === null ||
    typeof manifest !== "object" ||
    Array.isArray(manifest) ||
    manifest.format !== "orinoco-lite-runtime" ||
    manifest.manifest_version !== 1 ||
    typeof manifest.release !== "string" ||
    !manifest.release ||
    !Array.isArray(manifest.files)
  ) {
    throw new Error("Runtime manifest has an unsupported format");
  }

  const selected = [];
  const sourcePaths = new Set();
  const targetPaths = new Set();
  for (const entry of manifest.files) {
    if (
      entry === null ||
      typeof entry !== "object" ||
      Array.isArray(entry) ||
      !safeManifestPath(entry.path)
    ) {
      throw new Error("Runtime manifest contains an invalid file entry");
    }
    if (sourcePaths.has(entry.path)) {
      throw new Error(`Runtime manifest repeats a file: ${entry.path}`);
    }
    sourcePaths.add(entry.path);
    const target = targetPath(entry.path);
    if (target === null) continue;
    if (
      !target ||
      !DIGEST.test(entry.sha256) ||
      !Number.isSafeInteger(entry.size) ||
      entry.size < 0 ||
      (entry.mode !== 0o644 && entry.mode !== 0o755) ||
      targetPaths.has(target)
    ) {
      throw new Error(`Runtime editor resource is invalid: ${entry.path}`);
    }
    targetPaths.add(target);
    selected.push({ ...entry, target });
  }
  if (
    !targetPaths.has("index.html") ||
    [...SCHEMA_FILES].some((path) => !sourcePaths.has(path))
  ) {
    throw new Error(
      "Runtime does not contain the complete generic editor shell",
    );
  }

  const destinationRoot = resolve(destination);
  if (
    destinationRoot === runtimeRoot ||
    destinationRoot.startsWith(`${runtimeRoot}${sep}`)
  ) {
    throw new Error("Editor staging destination must be outside the runtime");
  }
  await mkdir(dirname(destinationRoot), { recursive: true });
  try {
    await lstat(destinationRoot);
    throw new Error("Editor staging destination already exists");
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }

  const temporary = await mkdtemp(
    join(dirname(destinationRoot), `.${basename(destinationRoot)}-`),
  );
  try {
    for (const entry of selected.sort((left, right) =>
      left.target.localeCompare(right.target),
    )) {
      const source = await regularFile(runtimeRoot, entry.path);
      if (source.status.size !== entry.size) {
        throw new Error(
          `Runtime editor resource has the wrong size: ${entry.path}`,
        );
      }
      const bytes = await readFile(source.path);
      if (digest(bytes) !== entry.sha256) {
        throw new Error(
          `Runtime editor resource failed its checksum: ${entry.path}`,
        );
      }
      const output = join(temporary, ...entry.target.split("/"));
      await mkdir(dirname(output), { recursive: true });
      await copyFile(source.path, output);
      await chmod(output, entry.mode);
    }
    await rename(temporary, destinationRoot);
  } catch (error) {
    await rm(temporary, { force: true, recursive: true });
    throw error;
  }
  return {
    destination: destinationRoot,
    files: selected.length,
    manifest_sha256: expectedManifestSha256,
    release: manifest.release,
  };
}

async function main(argv) {
  if (argv.length < 2 || argv.length > 3) {
    throw new Error(
      "Usage: stage-editor-runtime.mjs RUNTIME MANIFEST_SHA256 [DESTINATION]",
    );
  }
  const [runtime, expectedManifestSha256, destination] = argv;
  const report = await stageEditorRuntime({
    destination:
      destination ?? join("dist", "editor-runtime", expectedManifestSha256),
    expectedManifestSha256,
    runtime,
  });
  process.stdout.write(`${JSON.stringify(report)}\n`);
}

if (
  process.argv[1] !== undefined &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(
      `${error instanceof Error ? error.message : String(error)}\n`,
    );
    process.exitCode = 1;
  });
}

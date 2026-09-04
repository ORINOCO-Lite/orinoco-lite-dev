export interface MetadataRoots {
  annotations: string;
  records: string;
}

export const DEFAULT_RECORD_ROOT = "site-specific/metadata/records";

export function normalizedRepositoryDirectory(value: unknown): string | null {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > 1_024 ||
    value !== value.trim() ||
    value.startsWith("/") ||
    /[\\\u0000-\u001f\u007f]/.test(value)
  ) {
    return null;
  }
  const normalized = value.replace(/\/+$/, "");
  if (normalized.length === 0) return null;
  const parts = normalized.split("/");
  if (
    parts.some((part) => part.length === 0 || part === "." || part === "..")
  ) {
    return null;
  }
  return normalized;
}

export function metadataRoots(recordRoot: string): MetadataRoots {
  const normalized = normalizedRepositoryDirectory(recordRoot);
  if (normalized === null) throw new Error("invalid metadata record root");
  const parts = normalized.split("/");
  parts.pop();
  const parent = parts.join("/");
  return {
    annotations: `${parent ? `${parent}/` : ""}overlays/annotations`,
    records: normalized,
  };
}

export const DEFAULT_METADATA_ROOTS = metadataRoots(DEFAULT_RECORD_ROOT);

export function validRepositoryYamlPath(value: string): boolean {
  const lower = value.toLowerCase();
  if (
    value.length === 0 ||
    value.length > 1_024 ||
    value.startsWith("/") ||
    (!lower.endsWith(".yaml") && !lower.endsWith(".yml")) ||
    /[\\\u0000-\u001f\u007f]/.test(value)
  ) {
    return false;
  }
  return value
    .split("/")
    .every((part) => part.length > 0 && part !== "." && part !== "..");
}

export function validYamlPathBelow(value: string, root: string): boolean {
  const prefix = `${root}/`;
  if (!value.startsWith(prefix) || !validRepositoryYamlPath(value))
    return false;
  return value
    .slice(prefix.length)
    .split("/")
    .every((part) => !part.startsWith("."));
}

export function annotationPathForRecord(
  recordPath: string,
  roots: MetadataRoots,
): string {
  return `${roots.annotations}/${recordPath.slice(roots.records.length + 1)}`;
}

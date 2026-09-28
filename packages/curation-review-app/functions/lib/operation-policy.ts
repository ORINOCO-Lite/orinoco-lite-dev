import { HttpError } from "./http";

export const OPERATIONS = [
  "shacl_materialization",
  "automated_curation",
  "template_updates",
  "preview_editing",
] as const;
export type Operation = (typeof OPERATIONS)[number];

export function parseOperations(
  value: unknown,
): Partial<Record<Operation, boolean>> {
  if (value === undefined) return {};
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.entries(value).some(
      ([key, enabled]) =>
        !OPERATIONS.includes(key as Operation) || typeof enabled !== "boolean",
    )
  )
    throw new HttpError(
      403,
      "invalid_operation_policy",
      "pyproject.toml tool.orinoco.operations must map known operation names to true or false.",
    );
  return value as Partial<Record<Operation, boolean>>;
}

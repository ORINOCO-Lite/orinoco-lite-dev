import { parse } from "smol-toml";
import type { GitHubClient } from "./github";
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

export async function requireOperation(
  github: GitHubClient,
  repository: string,
  operation: Operation,
): Promise<void> {
  // Neither a workflow input nor a proposal's base/head supplies policy authority.
  const repo = (await github.json(`/repos/${repository}`)) as {
    default_branch?: string;
  };
  if (!repo || typeof repo.default_branch !== "string")
    throw new HttpError(
      403,
      "invalid_operation_policy",
      "GitHub did not identify the repository default branch.",
    );
  const base = await github.branchHead(repository, repo.default_branch);
  const contents = await github.contents(repository, [
    { key: "operation-policy", path: "pyproject.toml", ref: base.sha },
  ]);
  let config: any;
  try {
    config = (parse(contents.get("operation-policy") ?? "") as any).tool
      ?.orinoco;
    if (!config || typeof config !== "object" || Array.isArray(config))
      throw new Error();
  } catch {
    throw new HttpError(
      403,
      "invalid_operation_policy",
      "The default branch must contain valid pyproject.toml configuration.",
    );
  }
  if (parseOperations(config.operations)[operation] !== true)
    throw new HttpError(
      403,
      "operation_disabled",
      `Enable tool.orinoco.operations.${operation} in pyproject.toml on the repository default branch before using this operation.`,
    );
}

import { GitHubClient } from "./github";
import { parseRepository } from "./input";
import type { Env } from "./pages";
import { AppAuthentication, object } from "./workflow-access";

const SHA = /^[0-9a-f]{40}$/;

// GitHub's signed merge event and the gitlink in the open website PR are the
// coordination state. A non-fast-forward update is left for GitHub to resolve.
export async function advanceWebsiteGitlink(
  env: Env,
  payload: unknown,
  auth = new AppAuthentication(env),
): Promise<boolean> {
  const event = object(payload);
  if (event.action !== "closed") return false;
  const pull = object(event.pull_request);
  if (pull.merged !== true || typeof pull.body !== "string") return false;
  const links = [
    ...pull.body.matchAll(
      /^Website branch: https:\/\/github\.com\/([^/\s]+\/[^/\s]+)\/tree\/([^\s]+)$/gm,
    ),
  ];
  if (links.length !== 1) return false;
  const websiteRepository = parseRepository(links[0]![1]!);
  let branch: string;
  try {
    branch = decodeURIComponent(links[0]![2]!);
  } catch {
    return false;
  }
  if (
    !branch ||
    branch.length > 255 ||
    /[\x00-\x20~^:?*\[\\]/.test(branch) ||
    branch.includes("..")
  )
    return false;
  const metadataRepository = parseRepository(
    object(event.repository).full_name,
  );
  const metadataHead = object(pull.head).sha;
  const merged = pull.merge_commit_sha;
  const author = object(pull.user);
  if (
    !SHA.test(metadataHead) ||
    !SHA.test(merged) ||
    !Number.isSafeInteger(author.id) ||
    typeof author.login !== "string"
  )
    return false;
  const token = await auth.token(websiteRepository, true);
  try {
    const github = new GitHubClient(token.token, auth.fetcher);
    await github.requireCurator(websiteRepository, author.login, author.id);
    const owner = websiteRepository.split("/")[0];
    const query = new URLSearchParams({
      state: "open",
      head: `${owner}:${branch}`,
      per_page: "100",
    });
    const result = await github.json(
      `/repos/${websiteRepository}/pulls?${query}`,
    );
    if (!Array.isArray(result) || result.length !== 1) return false;
    const websitePull = object(result[0]);
    const head = object(websitePull.head);
    if (
      head.ref !== branch ||
      head.repo?.full_name !== websiteRepository ||
      !SHA.test(head.sha)
    )
      return false;
    const link = await github.siteSubmodule(websiteRepository, head.sha);
    if (
      link?.repository.toLowerCase() !== metadataRepository.toLowerCase() ||
      link.sha !== metadataHead
    )
      return false;
    const current = object(
      await github.json(`/repos/${websiteRepository}/git/commits/${head.sha}`),
    );
    const treeSha = object(current.tree).sha;
    if (!SHA.test(treeSha)) return false;
    const tree = object(
      await github.json(`/repos/${websiteRepository}/git/trees`, {
        method: "POST",
        body: JSON.stringify({
          base_tree: treeSha,
          tree: [
            {
              path: "site-specific",
              mode: "160000",
              type: "commit",
              sha: merged,
            },
          ],
        }),
      }),
    );
    if (!SHA.test(tree.sha)) return false;
    const commit = object(
      await github.json(`/repos/${websiteRepository}/git/commits`, {
        method: "POST",
        body: JSON.stringify({
          message: "chore: update merged site-specific metadata",
          tree: tree.sha,
          parents: [head.sha],
        }),
      }),
    );
    if (!SHA.test(commit.sha)) return false;
    await github.json(
      `/repos/${websiteRepository}/git/refs/heads/${encodeURIComponent(branch)}`,
      {
        method: "PATCH",
        body: JSON.stringify({ sha: commit.sha, force: false }),
      },
    );
    return true;
  } finally {
    await auth.revoke(token.token);
  }
}

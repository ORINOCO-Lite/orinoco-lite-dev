import { describe, expect, it, vi } from "vitest";
import { GitHubClient } from "../functions/lib/github";

function graphqlResponse(request: RequestInit): Response {
  const body = JSON.parse(String(request.body)) as {
    query: string;
    variables: Record<string, string>;
  };
  const count = [...body.query.matchAll(/blob[0-9]+:/g)].length;
  const repository: Record<string, unknown> = {};
  for (let index = 0; index < count; index += 1) {
    const value = `record ${body.variables[`expression${index}`]}\n`;
    repository[`blob${index}`] = {
      __typename: "Blob",
      byteSize: new TextEncoder().encode(value).byteLength,
      isBinary: false,
      isTruncated: false,
      text: value,
    };
  }
  return Response.json({ data: { repository } });
}

describe("GitHub blob batching", () => {
  it("loads a large review in bounded GraphQL requests", async () => {
    const fetchMock = vi.fn(
      async (_url: string | URL | Request, init?: RequestInit) =>
        graphqlResponse(init ?? {}),
    );
    const client = new GitHubClient("ghu_test", fetchMock);
    const requests = Array.from({ length: 41 }, (_, index) => ({
      key: `record:${index}`,
      path: `metadata/records/example/${index}.yaml`,
      ref: "a".repeat(40),
    }));
    const result = await client.contents("example/site", requests);
    expect(result).toHaveLength(41);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    for (const call of fetchMock.mock.calls) {
      expect(call[0]).toBe("https://api.github.com/graphql");
      expect(call[1]?.method).toBe("POST");
    }
  });

  it("rejects binary or truncated metadata", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        data: {
          repository: {
            blob0: {
              __typename: "Blob",
              byteSize: 10,
              isBinary: true,
              isTruncated: false,
              text: null,
            },
          },
        },
      }),
    );
    await expect(
      new GitHubClient("ghu_test", fetchMock).contents("example/site", [
        {
          key: "record",
          path: "metadata/records/example/one.yaml",
          ref: "a".repeat(40),
        },
      ]),
    ).rejects.toThrow("binary, truncated, or too large");
  });
});

describe("GitHub commit bounds", () => {
  it("rejects a proposal commit beyond its candidate-derived file limit", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        files: [
          { filename: "metadata/records/example/one.yaml" },
          { filename: "metadata/records/example/two.yaml" },
        ],
        sha: "a".repeat(40),
      }),
    );
    await expect(
      new GitHubClient("ghu_test", fetchMock).commit(
        "example/site",
        "a".repeat(40),
        1,
      ),
    ).rejects.toThrow("too many files");
  });
});

describe("GitHub comment result", () => {
  it("accepts only the requested pull-request comment URL", async () => {
    const validFetch = vi.fn(async () =>
      Response.json({
        html_url: "https://github.com/example/site/pull/42#issuecomment-12345",
      }),
    );
    await expect(
      new GitHubClient("ghu_test", validFetch).postComment(
        "example/site",
        42,
        "decision",
      ),
    ).resolves.toContain("issuecomment-12345");

    const wrongFetch = vi.fn(async () =>
      Response.json({
        html_url: "https://github.com/example/other/pull/42#issuecomment-12345",
      }),
    );
    await expect(
      new GitHubClient("ghu_test", wrongFetch).postComment(
        "example/site",
        42,
        "decision",
      ),
    ).rejects.toThrow("invalid comment");
  });
});

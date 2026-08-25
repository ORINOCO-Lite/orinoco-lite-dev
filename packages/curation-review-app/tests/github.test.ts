import { describe, expect, it, vi } from "vitest";
import {
  MAX_ARTIFACT_ARCHIVE_BYTES,
  MAX_REVIEW_PATHS,
} from "../functions/lib/bundle";
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

describe("GitHub fetch invocation", () => {
  it("calls an injected fetch implementation without a receiver", async () => {
    const receivers: unknown[] = [];
    const fetchMock = vi.fn(function (
      this: unknown,
      _input: string | URL | Request,
      init?: RequestInit,
    ) {
      receivers.push(this);
      if (this !== undefined) throw new TypeError("Illegal invocation");
      expect(init?.redirect).toBe("manual");
      return Promise.resolve(Response.json({ id: 1, login: "octocat" }));
    });

    await expect(
      new GitHubClient("ghu_test", fetchMock).currentUser(),
    ).resolves.toEqual({ id: 1, login: "octocat" });
    expect(receivers).toEqual([undefined]);
  });
});

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
    ).rejects.toThrow("too many metadata paths");
  });

  it("accepts 450 metadata paths across five API pages", async () => {
    const files = Array.from({ length: MAX_REVIEW_PATHS }, (_, index) => ({
      filename: `metadata/records/example/${index}.yaml`,
    }));
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const page = Number(new URL(String(input)).searchParams.get("page"));
      return Response.json({
        files: files.slice((page - 1) * 100, page * 100),
        sha: "a".repeat(40),
      });
    });

    const result = await new GitHubClient("ghu_test", fetchMock).commit(
      "example/site",
      "a".repeat(40),
      MAX_REVIEW_PATHS,
    );

    expect(result.files).toHaveLength(MAX_REVIEW_PATHS);
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });

  it("rejects a 451st path beyond the service-resource bound", async () => {
    const files = Array.from({ length: MAX_REVIEW_PATHS + 1 }, (_, index) => ({
      filename: `metadata/records/example/${index}.yaml`,
    }));
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const page = Number(new URL(String(input)).searchParams.get("page"));
      return Response.json({
        files: files.slice((page - 1) * 100, page * 100),
        sha: "a".repeat(40),
      });
    });

    await expect(
      new GitHubClient("ghu_test", fetchMock).commit(
        "example/site",
        "a".repeat(40),
        MAX_REVIEW_PATHS,
      ),
    ).rejects.toThrow("too many metadata paths");
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });
});

describe("GitHub Actions artifact download", () => {
  it("follows one authenticated GitHub redirect without forwarding credentials", async () => {
    const archive = new Uint8Array([80, 75, 1, 2]);
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        expect(init?.redirect).toBe("manual");
        if (url.startsWith("https://api.github.com/")) {
          expect(new Headers(init?.headers).get("authorization")).toBe(
            "Bearer ghu_test",
          );
          return new Response(null, {
            headers: {
              Location:
                "https://pipelines.actions.githubusercontent.com/results/archive.zip?sig=short-lived",
            },
            status: 302,
          });
        }
        expect(url).toContain("pipelines.actions.githubusercontent.com");
        expect(new Headers(init?.headers).has("authorization")).toBe(false);
        return new Response(archive, {
          headers: { "Content-Length": String(archive.byteLength) },
        });
      },
    );

    await expect(
      new GitHubClient("ghu_test", fetchMock).artifactArchive(
        "example/site",
        123,
      ),
    ).resolves.toEqual(archive);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("rejects unsafe redirects and declared oversized archives", async () => {
    const unsafe = vi.fn(
      async () =>
        new Response(null, {
          headers: { Location: "https://127.0.0.1/private" },
          status: 302,
        }),
    );
    await expect(
      new GitHubClient("ghu_test", unsafe).artifactArchive("example/site", 123),
    ).rejects.toThrow("invalid artifact download URL");

    const oversized = vi.fn(async (input: string | URL | Request) =>
      String(input).startsWith("https://api.github.com/")
        ? new Response(null, {
            headers: {
              Location:
                "https://pipelines.actions.githubusercontent.com/results/archive.zip",
            },
            status: 302,
          })
        : new Response(new Uint8Array(), {
            headers: {
              "Content-Length": String(MAX_ARTIFACT_ARCHIVE_BYTES + 1),
            },
          }),
    );
    await expect(
      new GitHubClient("ghu_test", oversized).artifactArchive(
        "example/site",
        123,
      ),
    ).rejects.toThrow("compressed size limit");
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

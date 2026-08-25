import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ReviewDiscovery,
  ReviewProposal,
  ShaclReviewBundle,
} from "../shared/contracts";
import App from "./App";
import { ARTIFACT_ID, proposal } from "../tests/fixtures";

function json(value: unknown, status = 200): Response {
  return Response.json(value, { status });
}

function installFetch(
  reviewProposal: ReviewProposal = proposal(),
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/session") {
        return json({
          authenticated: true,
          csrf_token: "csrf-token",
          login: "octocat",
        });
      }
      if (url.startsWith("/api/proposal?")) return json(reviewProposal);
      if (url === `/api/submit?artifact_id=${ARTIFACT_ID}`) {
        expect(init?.headers).toMatchObject({ "X-CSRF-Token": "csrf-token" });
        return json(
          {
            comment_url:
              "https://github.com/example/site/pull/42#issuecomment-99",
          },
          201,
        );
      }
      throw new Error(`Unexpected fetch: ${url}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function shaclBundle(): ShaclReviewBundle {
  return {
    format: "orinoco-shacl-review-bundle",
    records: [
      {
        pid: "example:one",
        rdf_turtle:
          '<https://example.test/one> <https://example.test/p> "x" .\n',
        schema_type: "example:Thing",
        source_path: "metadata/records/Thing/one.yaml",
        source_sha256: "b".repeat(64),
      },
    ],
    source_commit: "a".repeat(40),
    version: 2,
  };
}

function sendEditorBundle(
  frame: HTMLIFrameElement,
  value: ShaclReviewBundle = shaclBundle(),
  options: { origin?: string; source?: MessageEventSource | null } = {},
): void {
  act(() => {
    window.dispatchEvent(
      new MessageEvent("message", {
        data: {
          bundle: value,
          format: "orinoco-lite-shacl-bundle-message-v1",
          repository: "example/site",
        },
        origin: options.origin ?? window.location.origin,
        source: options.source ?? frame.contentWindow,
      }),
    );
  });
}

beforeEach(() => {
  window.history.replaceState(
    {},
    "",
    `/review/?artifact_id=${ARTIFACT_ID}&repository=example%2Fsite&pull_request=42`,
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("curation review interface", () => {
  it("shows responsive record diffs and one exclusive decision group per candidate", async () => {
    installFetch();
    const user = userEvent.setup();
    render(<App />);
    const first = await screen.findByRole("article", { name: "First record" });
    expect(
      within(first).getByText("Original first", { exact: false }),
    ).toBeInTheDocument();
    expect(
      within(first).getByText("Current first", { exact: false }),
    ).toBeInTheDocument();
    const accept = within(first).getByRole("radio", { name: "Accept" });
    const reject = within(first).getByRole("radio", { name: "Reject" });
    await user.click(accept);
    expect(accept).toBeChecked();
    await user.click(reject);
    expect(reject).toBeChecked();
    expect(accept).not.toBeChecked();
    expect(
      screen.getByRole("link", { name: "Edit in SHACL Vue" }),
    ).toHaveAttribute(
      "href",
      `/edit/?expected_head_sha=${proposal().head_sha}&pull_request=42&repository=example%2Fsite`,
    );
  });

  it("supports filtering, changed-only view, and keyboard decisions", async () => {
    installFetch();
    const user = userEvent.setup();
    render(<App />);
    const first = await screen.findByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });
    first.focus();
    await user.keyboard("a");
    expect(within(first).getByRole("radio", { name: "Accept" })).toBeChecked();
    await user.keyboard("j");
    expect(second).toHaveFocus();
    await user.keyboard("r");
    expect(within(second).getByRole("radio", { name: "Reject" })).toBeChecked();
    await user.click(
      screen.getByRole("checkbox", { name: "Changed at current head only" }),
    );
    expect(
      screen.queryByRole("article", { name: "Second record" }),
    ).not.toBeInTheDocument();
    await user.type(
      screen.getByRole("searchbox", { name: "Search records" }),
      "no match",
    );
    expect(
      screen.getByText("No records match the current filters."),
    ).toBeInTheDocument();
  });

  it("applies a bulk default only to unresolved records", async () => {
    installFetch();
    const user = userEvent.setup();
    render(<App />);
    const first = await screen.findByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });

    await user.click(within(first).getByRole("radio", { name: "Reject" }));
    await user.click(
      screen.getByRole("button", { name: "Accept all unresolved" }),
    );

    expect(within(first).getByRole("radio", { name: "Reject" })).toBeChecked();
    expect(within(second).getByRole("radio", { name: "Accept" })).toBeChecked();
    expect(screen.getByText("2/2")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Defer all unresolved" }),
    ).toBeDisabled();

    await user.click(within(second).getByRole("radio", { name: "Defer" }));
    expect(within(second).getByRole("radio", { name: "Defer" })).toBeChecked();
  });

  it("moves between visible records when a filter hides an intermediate card", async () => {
    const reviewProposal = proposal();
    const firstCandidate = reviewProposal.candidates[0];
    if (firstCandidate === undefined)
      throw new Error("missing fixture candidate");
    reviewProposal.candidates.push({
      ...firstCandidate,
      after: "pid: example:third\ntitle: Current third\n",
      before: "pid: example:third\ntitle: Original third\n",
      claim_sha256: `sha256:${"3".repeat(64)}`,
      friendly_id: "DRI-0003",
      label: "Third record",
      pid: "example:third",
      record_path: "metadata/records/example/third.yaml",
      source_record_id: "item:GHI789",
    });
    installFetch(reviewProposal);
    const user = userEvent.setup();
    render(<App />);
    const first = await screen.findByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });
    const third = screen.getByRole("article", { name: "Third record" });
    await user.click(within(second).getByRole("radio", { name: "Reject" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Decision" }),
      "unresolved",
    );
    first.focus();
    await user.keyboard("j");
    expect(third).toHaveFocus();
  });

  it("reveals and focuses the first unresolved record after incomplete submission", async () => {
    installFetch();
    const user = userEvent.setup();
    render(<App />);
    const first = await screen.findByRole("article", { name: "First record" });
    await user.click(within(first).getByRole("radio", { name: "Accept" }));
    const decisionFilter = screen.getByRole("combobox", { name: "Decision" });
    await user.selectOptions(decisionFilter, "accept");
    expect(
      screen.queryByRole("article", { name: "Second record" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Post decisions to GitHub" }),
    );
    expect(decisionFilter).toHaveValue("unresolved");
    await waitFor(() =>
      expect(
        screen.getByRole("article", { name: "Second record" }),
      ).toHaveFocus(),
    );
  });

  it("validates completion and posts the complete ordered decision payload", async () => {
    const fetchMock = installFetch();
    const user = userEvent.setup();
    render(<App />);
    const first = await screen.findByRole("article", { name: "First record" });
    await user.click(within(first).getByRole("radio", { name: "Accept" }));
    await user.click(
      screen.getByRole("button", { name: "Post decisions to GitHub" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "1 record still needs",
    );
    const second = screen.getByRole("article", { name: "Second record" });
    await user.click(within(second).getByRole("radio", { name: "Defer" }));
    await user.click(
      screen.getByRole("button", { name: "Post decisions to GitHub" }),
    );
    await screen.findByRole("link", { name: "View authenticated comment" });
    const call = fetchMock.mock.calls.find(
      ([url]) => url === `/api/submit?artifact_id=${ARTIFACT_ID}`,
    );
    expect(call).toBeDefined();
    const body = JSON.parse(String((call?.[1] as RequestInit).body)) as Record<
      string,
      unknown
    >;
    expect(body).not.toHaveProperty("reviewer");
    expect(
      (body.decisions as Array<Record<string, unknown>>).map(
        (item) => item.disposition,
      ),
    ).toEqual(["accept", "defer"]);
  });

  it("requires authentication without exposing repository data", async () => {
    const fetchMock = vi.fn(async () => json({ authenticated: false }));
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    expect(
      await screen.findByRole("link", { name: "Continue with GitHub" }),
    ).toHaveAttribute(
      "href",
      `/api/auth/start?artifact_id=${ARTIFACT_ID}&pull_request=42&repository=example%2Fsite`,
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  });
});

describe("repository-scoped curation discovery", () => {
  const discovery: ReviewDiscovery = {
    pull_requests: [
      {
        artifacts: [
          {
            created_at: "2026-08-25T04:30:00Z",
            expires_at: "2026-11-23T04:30:00Z",
            id: ARTIFACT_ID,
            name: `orinoco-curation-review-${"b".repeat(40)}`,
          },
        ],
        draft: true,
        head_sha: "a".repeat(40),
        number: 42,
        proposal_sha: "b".repeat(40),
        title: "Review source metadata",
      },
    ],
    repository: "example/site",
  };

  it("preserves the repository while asking an anonymous curator to sign in", async () => {
    window.history.replaceState({}, "", "/?repository=example%2Fsite");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ authenticated: false })),
    );
    render(<App />);
    expect(
      await screen.findByRole("link", { name: "Continue with GitHub" }),
    ).toHaveAttribute(
      "href",
      "/api/auth/discovery-start?repository=example%2Fsite",
    );
    expect(
      screen.getByRole("heading", { name: /example\/site/ }),
    ).toBeVisible();
  });

  it("prefills the sole relevant pull request and artifact after sign-in", async () => {
    window.history.replaceState({}, "", "/?repository=example%2Fsite");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/session") {
        return json({
          authenticated: true,
          csrf_token: "csrf-token",
          login: "octocat",
        });
      }
      if (String(input) === "/api/discovery?repository=example%2Fsite") {
        return json(discovery);
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", {
          name: "Open curation pull request",
        }),
      ).toHaveValue("42"),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: "Review artifact" }),
      ).toHaveValue(String(ARTIFACT_ID)),
    );
    expect(screen.getByDisplayValue("example/site")).toHaveAttribute(
      "readonly",
    );
    expect(screen.getByRole("button", { name: "Open review" })).toBeEnabled();
    expect(
      screen.getByRole("option", { name: /Draft PR #42/ }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("SHACL Vue browser-memory proposal wrapper", () => {
  it("starts a repository-bound curation journey", () => {
    window.history.replaceState({}, "", "/");
    render(<App />);
    expect(
      screen.getByRole("heading", {
        name: "Review or edit repository metadata",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "Repository" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Edit in SHACL Vue" }),
    ).not.toBeInTheDocument();
  });

  it("preserves exact existing-PR coordinates through user authentication", async () => {
    const source = "a".repeat(40);
    window.history.replaceState(
      {},
      "",
      `/edit/?repository=example%2Fsite&pull_request=42&expected_head_sha=${source}`,
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ authenticated: false })),
    );
    render(<App />);
    expect(
      await screen.findByRole("link", { name: "Continue with GitHub" }),
    ).toHaveAttribute(
      "href",
      `/api/auth/shacl-start?repository=example%2Fsite&expected_head_sha=${source}&pull_request=42`,
    );
  });

  it("embeds the same-origin editor and performs one acknowledged explicit write", async () => {
    window.history.replaceState({}, "", "/edit/?repository=example%2Fsite");
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/session") {
          return json({
            authenticated: true,
            csrf_token: "csrf-token",
            login: "octocat",
          });
        }
        if (url === "/api/shacl/propose") {
          expect(init?.headers).toMatchObject({
            "X-CSRF-Token": "csrf-token",
          });
          return json(
            {
              commit_sha: "c".repeat(40),
              commit_url: `https://github.com/example/site/commit/${"c".repeat(40)}`,
              pull_request: 43,
              pull_request_url: "https://github.com/example/site/pull/43",
            },
            201,
          );
        }
        throw new Error(`Unexpected fetch: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", {
      name: "Waiting for a SHACL Vue v2 bundle",
    });
    const frame = screen.getByTitle(
      "SHACL Vue metadata editor",
    ) as HTMLIFrameElement;
    expect(frame).toHaveAttribute(
      "src",
      "/api/shacl/editor?repository=example%2Fsite",
    );
    const editor = screen.getByRole("region", { name: "Edit in SHACL Vue" });
    expect(editor).toHaveAttribute("aria-busy", "true");
    expect(
      screen.getByText("Loading the exact-coordinate editor…"),
    ).toBeInTheDocument();
    fireEvent.load(frame);
    expect(editor).toHaveAttribute("aria-busy", "false");
    expect(
      screen.getByText(
        "Editor loaded. Generate the normal bundle when your edit is complete.",
      ),
    ).toBeInTheDocument();
    const bundle = shaclBundle();
    sendEditorBundle(frame, bundle);
    expect(
      await screen.findByRole("heading", { name: "1 edited record" }),
    ).toBeInTheDocument();
    expect(screen.getByText("example:one")).toBeInTheDocument();
    const propose = screen.getByRole("button", { name: "Propose via GitHub" });
    expect(propose).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: /I confirm this bundle contains no secrets/,
      }),
    );
    expect(propose).toBeEnabled();
    await user.click(propose);
    await screen.findByRole("link", { name: "Open draft pull request" });
    const write = fetchMock.mock.calls.find(
      ([url]) => url === "/api/shacl/propose",
    );
    const submitted = JSON.parse(
      String((write?.[1] as RequestInit).body),
    ) as Record<string, unknown>;
    expect(submitted).toEqual({
      acknowledge_public_data: true,
      bundle,
      format: "orinoco-lite-shacl-proposal-v1",
      repository: "example/site",
      target: { kind: "standalone" },
    });
    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
  });

  it("accepts the typed bundle message only from its same-origin iframe", async () => {
    window.history.replaceState({}, "", "/edit/?repository=example%2Fsite");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          authenticated: true,
          csrf_token: "csrf-token",
          login: "octocat",
        }),
      ),
    );
    render(<App />);
    await screen.findByRole("heading", {
      name: "Waiting for a SHACL Vue v2 bundle",
    });
    const frame = screen.getByTitle(
      "SHACL Vue metadata editor",
    ) as HTMLIFrameElement;
    sendEditorBundle(frame, shaclBundle(), {
      origin: "https://editor.example",
    });
    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
    sendEditorBundle(frame, shaclBundle(), { source: window });
    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
    sendEditorBundle(frame);
    expect(
      await screen.findByRole("heading", { name: "1 edited record" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Browser source: this embedded editor"),
    ).toBeInTheDocument();
  });

  it("binds the embedded editor to exact existing-PR coordinates", async () => {
    const source = "a".repeat(40);
    window.history.replaceState(
      {},
      "",
      `/edit/?repository=example%2Fsite&pull_request=42&expected_head_sha=${source}`,
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          authenticated: true,
          csrf_token: "csrf-token",
          login: "octocat",
        }),
      ),
    );
    render(<App />);
    const frame = (await screen.findByTitle(
      "SHACL Vue metadata editor",
    )) as HTMLIFrameElement;
    expect(frame).toHaveAttribute(
      "src",
      `/api/shacl/editor?repository=example%2Fsite&expected_head_sha=${source}&pull_request=42`,
    );
  });

  it("binds an existing-PR handoff to the received source commit", async () => {
    const source = "a".repeat(40);
    window.history.replaceState(
      {},
      "",
      `/edit/?repository=example%2Fsite&pull_request=42&expected_head_sha=${source}`,
    );
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/session") {
          return json({
            authenticated: true,
            csrf_token: "csrf-token",
            login: "octocat",
          });
        }
        const body = JSON.parse(String(init?.body)) as {
          target: Record<string, unknown>;
        };
        expect(body.target).toEqual({
          expected_head_sha: source,
          kind: "pull_request",
          pull_request: 42,
        });
        return json(
          {
            commit_sha: "c".repeat(40),
            commit_url: `https://github.com/example/site/commit/${"c".repeat(40)}`,
            pull_request: 42,
            pull_request_url: "https://github.com/example/site/pull/42",
          },
          201,
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", {
      name: "Waiting for a SHACL Vue v2 bundle",
    });
    const frame = screen.getByTitle(
      "SHACL Vue metadata editor",
    ) as HTMLIFrameElement;
    sendEditorBundle(frame);
    await screen.findByRole("heading", { name: "1 edited record" });
    expect(
      screen.getByRole("spinbutton", { name: "Draft pull request" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("radio", {
        name: "Create a branch and new draft pull request",
      }),
    ).toBeDisabled();
    expect(
      screen.getByText(`Bound to draft pull request #42 at`, { exact: false }),
    ).toHaveTextContent(source);
    await user.click(
      screen.getByRole("checkbox", {
        name: /I confirm this bundle contains no secrets/,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Propose via GitHub" }),
    );
    await screen.findByRole("link", { name: "Open draft pull request" });
  });
});

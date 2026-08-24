import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReviewProposal } from "../shared/contracts";
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

beforeEach(() => {
  window.history.replaceState(
    {},
    "",
    `/?artifact_id=${ARTIFACT_ID}&repository=example%2Fsite&pull_request=42`,
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

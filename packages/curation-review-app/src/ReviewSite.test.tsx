import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import reviewHtml from "../review/index.html?raw";
import type { ReviewProposal } from "../shared/contracts";
import { ARTIFACT_ID, proposal, submission } from "../tests/fixtures";
import ReviewSiteLoader, { isSharedGitHubPagesHostname } from "./ReviewSite";

const SERVICE_ORIGIN = "https://transport.example";

interface PopupMocks {
  closed: boolean;
  focusMock: ReturnType<typeof vi.fn>;
  postMessageMock: ReturnType<typeof vi.fn>;
}

type TestPopup = Window & PopupMocks;

function json(value: unknown, status = 200): Response {
  return Response.json(value, { status });
}

function config(): Record<string, unknown> {
  return {
    app_name: "Example source metadata review",
    format: "orinoco-curation-review-config",
    repository: "example/site",
    service_origin: SERVICE_ORIGIN,
    version: 1,
  };
}

function target(): string {
  const query = new URLSearchParams({
    artifact_id: String(ARTIFACT_ID),
    pull_request: "42",
    repository: "example/site",
  });
  return `/review/?${query.toString()}`;
}

function boundProposal(
  overrides: Partial<ReviewProposal> = {},
): ReviewProposal {
  return {
    ...proposal(),
    review_service_origin: SERVICE_ORIGIN,
    review_site_url: `${window.location.origin}/review/`,
    ...overrides,
  };
}

function installConfig(value: unknown = config()): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    expect(String(input)).toBe(`${window.location.origin}/review/config.json`);
    return json(value);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function installPopup(
  onOpen?: (url: string | URL | undefined, popup: TestPopup) => void,
): {
  open: ReturnType<typeof vi.fn>;
  popup: TestPopup;
} {
  const focusMock = vi.fn();
  const postMessageMock = vi.fn();
  const popup = {
    closed: false,
    focus: focusMock,
    focusMock,
    postMessage: postMessageMock,
    postMessageMock,
  } as unknown as TestPopup;
  const open = vi.spyOn(window, "open").mockImplementation((url) => {
    onOpen?.(url, popup);
    return popup;
  });
  return { open, popup };
}

function postFrom(
  popup: MessageEventSource,
  data: unknown,
  origin = SERVICE_ORIGIN,
): void {
  act(() => {
    window.dispatchEvent(
      new MessageEvent("message", {
        data,
        origin,
        source: popup,
      }),
    );
  });
}

function coordinates(nonce: string): Record<string, unknown> {
  return {
    artifact_id: ARTIFACT_ID,
    handoff_nonce: nonce,
    pull_request: 42,
    repository: "example/site",
  };
}

function ready(nonce: string): Record<string, unknown> {
  return {
    ...coordinates(nonce),
    format: "orinoco-lite-review-transport-ready-v1",
  };
}

function proposalMessage(
  nonce: string,
  reviewProposal: ReviewProposal = boundProposal(),
): Record<string, unknown> {
  return {
    ...coordinates(nonce),
    format: "orinoco-lite-review-proposal-message-v1",
    login: "octocat",
    proposal: reviewProposal,
  };
}

function postStarted(nonce: string): Record<string, unknown> {
  return {
    ...coordinates(nonce),
    format: "orinoco-lite-review-post-started-v1",
  };
}

function openedNonce(open: ReturnType<typeof vi.fn>): string {
  const last = open.mock.calls.at(-1);
  const openedUrl = new URL(String(last?.[0]));
  const nonce = openedUrl.searchParams.get("handoff_nonce");
  if (nonce === null) throw new Error("missing review handoff nonce");
  return nonce;
}

beforeEach(() => {
  window.history.replaceState({}, "", target());
  document.title = "";
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("deployed source-review document security", () => {
  it("ships a self-contained CSP and no-referrer policy without a frame-ancestors meta directive", () => {
    expect(reviewHtml).toContain('http-equiv="Content-Security-Policy"');
    expect(reviewHtml).toContain("default-src 'none'");
    expect(reviewHtml).toContain("connect-src 'self'");
    expect(reviewHtml).toContain("script-src 'self'");
    expect(reviewHtml).toContain('name="referrer" content="no-referrer"');
    expect(reviewHtml).not.toContain("frame-ancestors");
  });
});

describe("deployed source-review route", () => {
  it.each([
    ["github.io", true],
    ["owner.github.io", true],
    ["OWNER.GITHUB.IO", true],
    ["OWNER.GITHUB.IO.", true],
    ["Owner.GitHub.Io...", true],
    ["example.github.io.attacker.test", false],
    ["example.github.io.attacker.test.", false],
    ["notgithub.io", false],
    ["curation.example.org", false],
  ])("classifies %s shared-origin status exactly", (hostname, expected) => {
    expect(isSharedGitHubPagesHostname(hostname)).toBe(expected);
  });

  it("links an unbound route to this downstream's open curation proposals", async () => {
    window.history.replaceState({}, "", "/review/");
    installConfig();
    render(<ReviewSiteLoader />);

    const link = await screen.findByRole("link", {
      name: "View open curation pull requests on GitHub",
    });
    expect(link).toHaveAttribute(
      "href",
      "https://github.com/example/site/pulls?q=is%3Apr+is%3Aopen+label%3Acuration-review",
    );
  });

  it("loads strict site-owned configuration and opens only the transport popup", async () => {
    const fetchMock = installConfig();
    const { open, popup } = installPopup();
    const user = userEvent.setup();
    render(<ReviewSiteLoader />);

    const connect = await screen.findByRole("button", {
      name: "Connect with GitHub",
    });
    expect(document.title).toBe("Example source metadata review");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: "Shared github.io security boundary",
      }),
    ).not.toBeInTheDocument();
    expect(connect).toBeEnabled();

    await user.click(connect);
    expect(open).toHaveBeenCalledTimes(1);
    const openedUrl = new URL(String(open.mock.calls[0]?.[0]));
    expect(openedUrl.origin).toBe(SERVICE_ORIGIN);
    expect(openedUrl.pathname).toBe("/api/transport");
    expect(Object.fromEntries(openedUrl.searchParams)).toMatchObject({
      artifact_id: String(ARTIFACT_ID),
      kind: "review",
      pull_request: "42",
      repository: "example/site",
      review_origin: window.location.origin,
    });
    expect(openedUrl.searchParams.get("handoff_nonce")).toMatch(
      /^[0-9a-f]{64}$/,
    );
    expect(popup.focusMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Complete GitHub sign-in in the transport window.",
    );
  });

  it("installs the listener before opening and answers one early ready message", async () => {
    installConfig();
    const { open, popup } = installPopup((url, source) => {
      const nonce = new URL(String(url)).searchParams.get("handoff_nonce");
      if (nonce === null) throw new Error("missing early handoff nonce");
      queueMicrotask(() => postFrom(source, ready(nonce)));
    });
    const user = userEvent.setup();
    render(<ReviewSiteLoader />);
    await user.click(
      await screen.findByRole("button", { name: "Connect with GitHub" }),
    );
    const nonce = openedNonce(open);
    const request = {
      ...coordinates(nonce),
      format: "orinoco-lite-review-proposal-request-v1",
    };
    await waitFor(() =>
      expect(popup.postMessageMock).toHaveBeenCalledWith(
        request,
        SERVICE_ORIGIN,
      ),
    );
    postFrom(popup, ready(nonce));
    expect(
      popup.postMessageMock.mock.calls.filter(
        ([value]) =>
          (value as Record<string, unknown>).format ===
          "orinoco-lite-review-proposal-request-v1",
      ),
    ).toHaveLength(1);
  });

  it("ignores wrong source, origin, coordinates, and keys during handshake", async () => {
    installConfig();
    const { open, popup } = installPopup();
    const user = userEvent.setup();
    render(<ReviewSiteLoader />);
    await user.click(
      await screen.findByRole("button", { name: "Connect with GitHub" }),
    );
    const nonce = openedNonce(open);
    postFrom(popup, ready(nonce), "https://attacker.example");
    postFrom(window, ready(nonce));
    postFrom(popup, { ...ready(nonce), pull_request: 43 });
    postFrom(popup, { ...ready(nonce), extra: true });
    expect(popup.postMessageMock).not.toHaveBeenCalled();

    postFrom(popup, ready(nonce));
    expect(popup.postMessageMock).toHaveBeenCalledTimes(1);
    const validProposal = proposalMessage(nonce);
    postFrom(popup, validProposal, "https://attacker.example");
    postFrom(window, validProposal);
    postFrom(popup, { ...validProposal, repository: "example/other" });
    postFrom(popup, { ...validProposal, extra: true });
    expect(screen.queryByRole("article")).not.toBeInTheDocument();

    postFrom(popup, validProposal);
    expect(
      await screen.findByRole("article", { name: "First record" }),
    ).toBeInTheDocument();
    postFrom(popup, validProposal);
    expect(screen.getAllByRole("article")).toHaveLength(2);
  });

  it.each([
    ["site URL", { review_site_url: "https://other.example/review/" }],
    [
      "query-bearing site URL",
      {
        review_site_url: `${window.location.origin}/review/?artifact_id=${ARTIFACT_ID}`,
      },
    ],
    ["service origin", { review_service_origin: "https://other.example" }],
  ])(
    "rejects a proposal with the wrong bound %s",
    async (_label, overrides) => {
      installConfig();
      const { open, popup } = installPopup();
      const user = userEvent.setup();
      render(<ReviewSiteLoader />);
      await user.click(
        await screen.findByRole("button", { name: "Connect with GitHub" }),
      );
      const nonce = openedNonce(open);
      postFrom(popup, ready(nonce));
      postFrom(popup, proposalMessage(nonce, boundProposal(overrides)));
      expect(screen.getByRole("status")).toHaveTextContent(
        "authenticated transport returned an invalid proposal",
      );
      expect(screen.queryByRole("article")).not.toBeInTheDocument();
    },
  );

  it("sends one exact submission and accepts one exact result", async () => {
    installConfig();
    const { open, popup } = installPopup();
    const user = userEvent.setup();
    render(<ReviewSiteLoader />);
    await user.click(
      await screen.findByRole("button", { name: "Connect with GitHub" }),
    );
    const nonce = openedNonce(open);
    postFrom(popup, ready(nonce));
    postFrom(popup, proposalMessage(nonce));
    const first = await screen.findByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });
    expect(screen.getByText(/Connected as/)).toHaveTextContent(
      "Connected as octocat",
    );

    await user.click(within(first).getByRole("radio", { name: "Accept" }));
    await user.click(within(second).getByRole("radio", { name: "Defer" }));
    const submit = screen.getByRole("button", {
      name: "Review decisions before posting",
    });
    act(() => {
      submit.click();
      submit.click();
    });
    expect(
      screen.getByRole("heading", {
        name: "Confirm the complete decision state",
      }),
    ).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(
      popup.postMessageMock.mock.calls.filter(
        ([value]) =>
          (value as Record<string, unknown>).format ===
          "orinoco-lite-review-submission-message-v1",
      ),
    ).toHaveLength(0);
    const confirm = screen.getByRole("button", {
      name: "Confirm and post to GitHub",
    });
    act(() => {
      confirm.click();
      confirm.click();
    });
    const submitted = {
      ...coordinates(nonce),
      format: "orinoco-lite-review-submission-message-v1",
      submission: submission(),
    };
    await waitFor(() =>
      expect(popup.postMessageMock).toHaveBeenCalledWith(
        submitted,
        SERVICE_ORIGIN,
      ),
    );
    expect(
      popup.postMessageMock.mock.calls.filter(
        ([value]) =>
          (value as Record<string, unknown>).format ===
          "orinoco-lite-review-submission-message-v1",
      ),
    ).toHaveLength(1);

    const result = {
      ...coordinates(nonce),
      comment_url: "https://github.com/example/site/pull/42#issuecomment-99",
      error: null,
      format: "orinoco-lite-review-submission-result-v1",
      retry_safe: false,
    };
    postFrom(popup, result);
    expect(
      screen.queryByRole("link", { name: "View authenticated comment" }),
    ).not.toBeInTheDocument();

    const started = postStarted(nonce);
    postFrom(popup, started, "https://attacker.example");
    postFrom(window, started);
    postFrom(popup, { ...started, repository: "example/other" });
    postFrom(popup, { ...started, extra: true });
    postFrom(popup, result, "https://attacker.example");
    postFrom(window, result);
    postFrom(popup, { ...result, artifact_id: ARTIFACT_ID + 1 });
    postFrom(popup, { ...result, extra: true });
    expect(
      screen.queryByRole("link", { name: "View authenticated comment" }),
    ).not.toBeInTheDocument();

    postFrom(popup, started);
    expect(
      screen.getByText("Posting the confirmed decisions to GitHub…"),
    ).toBeVisible();
    postFrom(popup, result);
    expect(
      await screen.findByRole("link", { name: "View authenticated comment" }),
    ).toHaveAttribute("href", result.comment_url);
    postFrom(popup, result);
    expect(
      screen.getAllByRole("link", { name: "View authenticated comment" }),
    ).toHaveLength(1);
  });

  it("preserves decisions and reconnects after an explicit failure result", async () => {
    installConfig();
    const { open, popup } = installPopup();
    const user = userEvent.setup();
    render(<ReviewSiteLoader />);
    await user.click(
      await screen.findByRole("button", { name: "Connect with GitHub" }),
    );
    const firstNonce = openedNonce(open);
    postFrom(popup, ready(firstNonce));
    postFrom(popup, proposalMessage(firstNonce));
    const first = await screen.findByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });
    const accept = within(first).getByRole("radio", { name: "Accept" });
    const defer = within(second).getByRole("radio", { name: "Defer" });
    await user.click(accept);
    await user.click(defer);
    await user.click(
      screen.getByRole("button", { name: "Review decisions before posting" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Confirm and post to GitHub" }),
    );
    postFrom(popup, postStarted(firstNonce));
    postFrom(popup, {
      ...coordinates(firstNonce),
      comment_url: null,
      error: "GitHub rejected the authenticated comment.",
      format: "orinoco-lite-review-submission-result-v1",
      retry_safe: true,
    });

    const reopen = await screen.findByRole("button", {
      name: "Reopen GitHub transport",
    });
    expect(
      screen.getByText(/Check the pull request, then reopen/),
    ).toBeVisible();
    expect(accept).toBeChecked();
    expect(defer).toBeChecked();

    await user.click(reopen);
    expect(open).toHaveBeenCalledTimes(2);
    const secondNonce = openedNonce(open);
    expect(secondNonce).not.toBe(firstNonce);
    postFrom(popup, ready(secondNonce));
    postFrom(popup, proposalMessage(secondNonce));
    expect(accept).toBeChecked();
    expect(defer).toBeChecked();

    await user.click(
      screen.getByRole("button", { name: "Review decisions before posting" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Confirm and post to GitHub" }),
    );
    expect(popup.postMessageMock).toHaveBeenCalledWith(
      {
        ...coordinates(secondNonce),
        format: "orinoco-lite-review-submission-message-v1",
        submission: submission(),
      },
      SERVICE_ORIGIN,
    );

    postFrom(popup, postStarted(secondNonce));
    postFrom(popup, {
      ...coordinates(secondNonce),
      comment_url: null,
      error: "The response from GitHub was incomplete.",
      format: "orinoco-lite-review-submission-result-v1",
      retry_safe: false,
    });
    expect(
      screen.queryByRole("button", { name: "Reopen GitHub transport" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/GitHub post result is uncertain/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Posting…" })).toBeDisabled();
  });

  it("reports a blocked or closed popup", async () => {
    installConfig();
    vi.spyOn(window, "open").mockReturnValue(null);
    const user = userEvent.setup();
    const { unmount } = render(<ReviewSiteLoader />);
    await user.click(
      await screen.findByRole("button", { name: "Connect with GitHub" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent("Allow the GitHub");

    unmount();
    installConfig();
    const { popup } = installPopup();
    render(<ReviewSiteLoader />);
    const connect = await screen.findByRole("button", {
      name: "Connect with GitHub",
    });
    vi.useFakeTimers();
    act(() => connect.click());
    popup.closed = true;
    act(() => vi.advanceTimersByTime(250));
    expect(screen.getByRole("status")).toHaveTextContent(
      "transport window was closed",
    );
  });

  it("allows the OAuth window and times out each later transport phase", async () => {
    installConfig();
    const { open, popup } = installPopup();
    const { unmount } = render(<ReviewSiteLoader />);
    const connect = await screen.findByRole("button", {
      name: "Connect with GitHub",
    });
    vi.useFakeTimers();
    act(() => connect.click());
    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Complete GitHub sign-in",
    );
    act(() => vi.advanceTimersByTime(540_000));
    expect(screen.getByRole("status")).toHaveTextContent(
      "GitHub sign-in did not complete before it expired",
    );

    vi.useRealTimers();
    unmount();
    installConfig();
    const handshakeRender = render(<ReviewSiteLoader />);
    const reconnect = await screen.findByRole("button", {
      name: "Connect with GitHub",
    });
    await userEvent.setup().click(reconnect);
    const nonce = openedNonce(open);
    vi.useFakeTimers();
    postFrom(popup, ready(nonce));
    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByRole("status")).toHaveTextContent(
      "did not return a proposal in time",
    );

    vi.useRealTimers();
    handshakeRender.unmount();
    installConfig();
    render(<ReviewSiteLoader />);
    const submitConnect = await screen.findByRole("button", {
      name: "Connect with GitHub",
    });
    await userEvent.setup().click(submitConnect);
    const submitNonce = openedNonce(open);
    postFrom(popup, ready(submitNonce));
    postFrom(popup, proposalMessage(submitNonce));
    const first = await screen.findByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });
    await userEvent
      .setup()
      .click(within(first).getByRole("radio", { name: "Accept" }));
    await userEvent
      .setup()
      .click(within(second).getByRole("radio", { name: "Defer" }));
    vi.useFakeTimers();
    act(() =>
      screen
        .getByRole("button", { name: "Review decisions before posting" })
        .click(),
    );
    act(() =>
      screen
        .getByRole("button", { name: "Confirm and post to GitHub" })
        .click(),
    );
    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByRole("status")).toHaveTextContent(
      "did not acknowledge the decisions",
    );
  });

  it("rejects configuration outside the exact generated contract", async () => {
    installConfig({ ...config(), legacy_review_url: SERVICE_ORIGIN });
    render(<ReviewSiteLoader />);
    expect(
      await screen.findByRole("heading", {
        name: "The deployed reviewer could not start",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("The review configuration is invalid."),
    ).toBeVisible();
  });

  it("refuses coordinates for another downstream repository", async () => {
    installConfig({ ...config(), repository: "example/other" });
    render(<ReviewSiteLoader />);
    expect(
      await screen.findByRole("heading", {
        name: "The proposal belongs to another repository",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/bound to example\/other/)).toBeVisible();
  });
});

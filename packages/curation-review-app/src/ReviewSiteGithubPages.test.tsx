/**
 * @vitest-environment jsdom
 * @vitest-environment-options {"url":"https://owner.github.io/example/review/"}
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ReviewSiteLoader from "./ReviewSite";

const CONFIG = {
  app_name: "Example source metadata review",
  format: "orinoco-curation-review-config",
  repository: "example/site",
  service_origin: "https://transport.example",
  version: 1,
};

beforeEach(() => {
  window.history.replaceState(
    {},
    "",
    "/example/review/?artifact_id=123&pull_request=42&repository=example%2Fsite",
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(CONFIG)),
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("shared GitHub Pages acknowledgement", () => {
  it("requires a visible in-memory acknowledgement before connecting", async () => {
    const user = userEvent.setup();
    const first = render(<ReviewSiteLoader />);
    const connect = await screen.findByRole("button", {
      name: "Connect with GitHub",
    });

    expect(
      screen.getByRole("heading", {
        name: "Shared github.io security boundary",
      }),
    ).toBeVisible();
    expect(screen.getByText(/Every project page/)).toBeVisible();
    expect(connect).toBeDisabled();

    await user.click(
      screen.getByRole("checkbox", {
        name: /I understand this shared-origin risk/,
      }),
    );
    expect(connect).toBeEnabled();

    first.unmount();
    render(<ReviewSiteLoader />);
    expect(
      await screen.findByRole("button", { name: "Connect with GitHub" }),
    ).toBeDisabled();
  });
});

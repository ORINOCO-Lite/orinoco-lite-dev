import { describe, expect, it } from "vitest";
import {
  parseSubmission,
  submissionComment,
  verifySubmission,
} from "../functions/lib/submission";
import { proposal, submission } from "./fixtures";

describe("authenticated submission envelope", () => {
  it("accepts only the complete ordered current candidate set", () => {
    const parsed = parseSubmission(submission());
    const verified = verifySubmission(parsed, proposal());
    expect(verified.repository).toBe("example/site");
    expect(verified.decisions.map((item) => item.disposition)).toEqual([
      "accept",
      "defer",
    ]);
  });

  it("rejects stale heads and incomplete decisions", () => {
    expect(() =>
      verifySubmission(
        { ...submission(), head_sha: "d".repeat(40) },
        proposal(),
      ),
    ).toThrow("no longer matches");
    expect(() =>
      verifySubmission(
        { ...submission(), decisions: submission().decisions.slice(0, 1) },
        proposal(),
      ),
    ).toThrow("no longer matches");
  });

  it("rejects identity fields and unexpected browser fields", () => {
    expect(() =>
      parseSubmission({ ...submission(), reviewer: "octocat" }),
    ).toThrow("missing or unexpected fields");
  });

  it("rejects a string or fractional pull-request number", () => {
    expect(() =>
      parseSubmission({ ...submission(), pull_request: "42" }),
    ).toThrow("positive integer");
    expect(() =>
      parseSubmission({ ...submission(), pull_request: 42.5 }),
    ).toThrow("positive integer");
  });

  it("renders one exact command and JSON object without reviewer identity", () => {
    const payload = submission();
    const body = submissionComment(payload);
    expect(body.startsWith("/curation submit\n\n```json\n{")).toBe(true);
    expect(body.endsWith("\n```")).toBe(true);
    expect(body).not.toContain("reviewer");
    expect(
      JSON.parse(body.slice(body.indexOf("{"), body.lastIndexOf("}") + 1)),
    ).toEqual(payload);
  });
});

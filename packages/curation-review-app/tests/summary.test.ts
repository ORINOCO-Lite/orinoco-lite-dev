import { describe, expect, it } from "vitest";
import { HttpError } from "../functions/lib/http";
import { parseProposalSummary } from "../functions/lib/summary";
import { MAX_GITHUB_TEXT_LENGTH } from "../shared/contracts";
import { CLAIM_ONE, PROPOSAL_SHA, summary } from "./fixtures";

describe("visible proposal summary", () => {
  it("parses the exact accessible rendering", () => {
    const result = parseProposalSummary(summary());
    expect(result.adapter).toBe("zotero");
    expect(result.proposal_sha).toBe(PROPOSAL_SHA);
    expect(result.source_coordinate).toEqual({
      group: 6197458,
      library_version: 451,
    });
    expect(result.candidates).toHaveLength(2);
    expect(result.candidates[0]).toMatchObject({
      blockers: [],
      claim_sha256: CLAIM_ONE,
      friendly_id: "DRI-0001",
      label: "First record",
      operation: "modify",
      pid: "example:first",
    });
    expect(result.candidates[1]?.blockers).toEqual([
      "Placeholder source URL requires attention",
    ]);
  });

  it("rejects duplicate candidate identity", () => {
    const duplicate = summary().replace("example:second", "example:first");
    expect(() => parseProposalSummary(duplicate)).toThrowError(HttpError);
    const duplicateFriendlyId = summary().replace("DRI-0002", "DRI-0001");
    expect(() => parseProposalSummary(duplicateFriendlyId)).toThrow(
      "friendly ID",
    );
  });

  it("rejects unexpected candidate fields", () => {
    const changed = summary().replace(
      "- Source record: `item:ABC123`",
      "- Hidden token: `abc`\n- Source record: `item:ABC123`",
    );
    expect(() => parseProposalSummary(changed)).toThrow(
      "unexpected detail fields",
    );
  });

  it("rejects a hidden or missing candidate review", () => {
    expect(() =>
      parseProposalSummary(
        summary().replace("## Candidate review", "<!-- Candidate review -->"),
      ),
    ).toThrow("missing the ## Candidate review section");
  });

  it("rejects a summary beyond GitHub's pull-request text limit", () => {
    expect(() =>
      parseProposalSummary(summary() + "x".repeat(MAX_GITHUB_TEXT_LENGTH)),
    ).toThrow("too large");
  });

  it("stops candidate parsing at later pull-request prose", () => {
    const result = parseProposalSummary(
      `${summary()}\n\n## Merge instructions\n\nUse a merge commit.`,
    );
    expect(result.candidates).toHaveLength(2);
  });

  it("rejects non-normal record paths", () => {
    for (const path of [
      "metadata/records/example/../first.yaml",
      "metadata/records/example//first.yaml",
      "metadata/records/./first.yaml",
      "metadata/records/.hidden/first.yaml",
    ]) {
      expect(() =>
        parseProposalSummary(
          summary().replace("metadata/records/example/first.yaml", path),
        ),
      ).toThrow("Record path is invalid");
    }
  });
});

import type { CurationSubmission, ReviewProposal } from "../shared/contracts";

export const BASE_SHA = "a".repeat(40);
export const PROPOSAL_SHA = "b".repeat(40);
export const HEAD_SHA = "c".repeat(40);
export const CLAIM_ONE = `sha256:${"1".repeat(64)}`;
export const CLAIM_TWO = `sha256:${"2".repeat(64)}`;

export function summary(): string {
  return `# Metadata curation

The Files changed view is authoritative.

## Curation proposal

- Adapter: \`zotero\`
- Proposal commit: \`${PROPOSAL_SHA}\`
- Source coordinate:

\`\`\`json
{"group":6197458,"library_version":451}
\`\`\`

## Candidate review

### DRI-0001 — First record

- PID: \`example:first\`
- Source record: \`item:ABC123\`
- Record path: \`metadata/records/example/first.yaml\`
- Operation: \`modify\`
- Claim SHA-256: \`${CLAIM_ONE}\`
- Blockers: None

### DRI-0002 — Second record

- PID: \`example:second\`
- Source record: \`item:DEF456\`
- Record path: \`metadata/records/example/second.yaml\`
- Operation: \`add\`
- Claim SHA-256: \`${CLAIM_TWO}\`
- Blockers:
  - Placeholder source URL requires attention`;
}

export function generatedSummary(candidateCount: number): string {
  const candidates = Array.from({ length: candidateCount }, (_, index) => {
    const identity = String(index + 1).padStart(4, "0");
    return `### DRI-${identity} — Record ${identity}

- PID: \`example:record-${identity}\`
- Source record: \`item:${identity}\`
- Record path: \`metadata/records/example/record-${identity}.yaml\`
- Operation: \`add\`
- Claim SHA-256: \`${CLAIM_ONE}\`
- Blockers: None`;
  }).join("\n\n");
  return `# Metadata curation

## Curation proposal

- Adapter: \`zotero\`
- Proposal commit: \`${PROPOSAL_SHA}\`
- Source coordinate:

\`\`\`json
{"group":6197458,"library_version":451}
\`\`\`

## Candidate review

${candidates}`;
}

export function proposal(): ReviewProposal {
  return {
    adapter: "zotero",
    candidates: [
      {
        after: "pid: example:first\ntitle: Current first\n",
        before: "pid: example:first\ntitle: Original first\n",
        blockers: [],
        claim_sha256: CLAIM_ONE,
        friendly_id: "DRI-0001",
        label: "First record",
        operation: "modify",
        pid: "example:first",
        record_path: "metadata/records/example/first.yaml",
        source_record_id: "item:ABC123",
      },
      {
        after: null,
        before: null,
        blockers: ["Placeholder source URL requires attention"],
        claim_sha256: CLAIM_TWO,
        friendly_id: "DRI-0002",
        label: "Second record",
        operation: "add",
        pid: "example:second",
        record_path: "metadata/records/example/second.yaml",
        source_record_id: "item:DEF456",
      },
    ],
    head_sha: HEAD_SHA,
    proposal_sha: PROPOSAL_SHA,
    pull_request: 42,
    pull_request_url: "https://github.com/example/site/pull/42",
    repository: "example/site",
    source_coordinate: { group: 6197458, library_version: 451 },
  };
}

export function submission(): CurationSubmission {
  return {
    adapter: "zotero",
    decisions: [
      {
        disposition: "accept",
        operation: "modify",
        pid: "example:first",
        record_path: "metadata/records/example/first.yaml",
      },
      {
        disposition: "defer",
        operation: "add",
        pid: "example:second",
        record_path: "metadata/records/example/second.yaml",
      },
    ],
    format: "orinoco-lite-curation-submission-v1",
    head_sha: HEAD_SHA,
    proposal_sha: PROPOSAL_SHA,
    pull_request: 42,
    repository: "example/site",
    source_coordinate: { group: 6197458, library_version: 451 },
  };
}

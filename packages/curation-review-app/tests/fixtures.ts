import { strToU8, zipSync } from "fflate";
import type { ReviewBundle } from "../functions/lib/bundle";
import type { CurationSubmission, ReviewProposal } from "../shared/contracts";

export const BASE_SHA = "a".repeat(40);
export const PROPOSAL_SHA = "b".repeat(40);
export const HEAD_SHA = "c".repeat(40);
export const CLAIM_ONE = `sha256:${"1".repeat(64)}`;
export const CLAIM_TWO = `sha256:${"2".repeat(64)}`;
export const ARTIFACT_ID = 123456789;
export const WORKFLOW_RUN_ID = 987654321;
export const ORINOCO_CONFIG = `contract_version: 2
site:
  name: Example site
  base_url: https://site.example/
  repository: example/site
  curation_service: https://review.example/
`;

export function proposalCommitMessage(): string {
  return `[DATALAD RUNCMD] chore(curation): propose zotero metadata

Curation-Adapter: zotero
Curation-Adapter-Agent: urn:example:agent
Curation-Metadata-Base: ${BASE_SHA}
Curation-Source: {"group":6197458,"library_version":451}

=== Do not change lines below ===
{"cmd":"trusted proposal command","inputs":[],"outputs":[]}
^^^ Do not change lines above ^^^`;
}

export function reviewBundle(): ReviewBundle {
  return {
    adapter: "zotero",
    candidates: [
      {
        blockers: [],
        claim_sha256: CLAIM_ONE,
        friendly_id: "DRI-0001",
        label: "First record",
        operation: "modify",
        paths: [
          "metadata/records/example/first.yaml",
          "metadata/overlays/annotations/example/first.yaml",
        ],
        pid: "example:first",
        record_path: "metadata/records/example/first.yaml",
        source_namespace: "zotero:group:6197458",
        source_record_id: "item:ABC123",
      },
      {
        blockers: ["Placeholder source URL requires attention"],
        claim_sha256: CLAIM_TWO,
        friendly_id: "DRI-0002",
        label: "Second record",
        operation: "add",
        paths: [
          "metadata/records/example/second.yaml",
          "metadata/overlays/annotations/example/second.yaml",
        ],
        pid: "example:second",
        record_path: "metadata/records/example/second.yaml",
        source_namespace: "zotero:group:6197458",
        source_record_id: "item:DEF456",
      },
    ],
    format: "orinoco-lite-curation-review-bundle-v1",
    metadata_base_sha: BASE_SHA,
    proposal_sha: PROPOSAL_SHA,
    pull_request: 42,
    repository: "example/site",
    source_coordinate: { group: 6197458, library_version: 451 },
    workflow_run_id: WORKFLOW_RUN_ID,
  };
}

export function reviewBundleArchive(
  value: unknown = reviewBundle(),
): Uint8Array {
  return zipSync({
    "review-bundle.json": strToU8(JSON.stringify(value)),
  });
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
        source_namespace: "zotero:group:6197458",
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
        source_namespace: "zotero:group:6197458",
        source_record_id: "item:DEF456",
      },
    ],
    head_sha: HEAD_SHA,
    proposal_sha: PROPOSAL_SHA,
    pull_request: 42,
    pull_request_url: "https://github.com/example/site/pull/42",
    repository: "example/site",
    review_service_origin: "https://review.example",
    review_site_url: "https://site.example/review/",
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

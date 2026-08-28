import { strToU8, zipSync } from "fflate";
import { describe, expect, it } from "vitest";
import {
  MAX_REVIEW_BUNDLE_BYTES,
  MAX_REVIEW_CANDIDATES,
  parseReviewBundle,
} from "../functions/lib/bundle";
import { metadataRoots } from "../shared/metadata";
import { CLAIM_ONE, reviewBundle, reviewBundleArchive } from "./fixtures";

function centralDirectory(archive: Uint8Array): number {
  const data = new DataView(
    archive.buffer,
    archive.byteOffset,
    archive.byteLength,
  );
  let offset = archive.length - 22;
  while (data.getUint32(offset, true) !== 0x06054b50) offset -= 1;
  return data.getUint32(offset + 16, true);
}

describe("ephemeral review bundle", () => {
  it("parses the exact versioned bundle and allows ordinary presentation punctuation", () => {
    const bundle = reviewBundle();
    const first = bundle.candidates[0];
    if (first === undefined) throw new Error("missing fixture candidate");
    first.label = "<First> *record* [for review] @curator";
    first.blockers = ["Use `GitHub` & inspect #details"];

    const parsed = parseReviewBundle(reviewBundleArchive(bundle));

    expect(parsed).toEqual(bundle);
  });

  it("accepts canonical .yml record and annotation paths", () => {
    const bundle = reviewBundle();
    const first = bundle.candidates[0];
    if (first === undefined) throw new Error("missing fixture candidate");
    first.record_path = "site-specific/metadata/records/example/first.yml";
    first.paths = [
      first.record_path,
      "site-specific/metadata/overlays/annotations/example/first.yml",
    ];

    expect(
      parseReviewBundle(reviewBundleArchive(bundle)).candidates[0]?.record_path,
    ).toBe(first.record_path);
  });

  it("validates an unchanged legacy bundle against legacy roots", () => {
    const bundle = reviewBundle();
    for (const candidate of bundle.candidates) {
      candidate.record_path = candidate.record_path.replace(
        "site-specific/metadata/records/",
        "metadata/records/",
      );
      candidate.paths = candidate.paths.map((path) =>
        path
          .replace("site-specific/metadata/records/", "metadata/records/")
          .replace(
            "site-specific/metadata/overlays/annotations/",
            "metadata/overlays/annotations/",
          ),
      );
    }

    expect(
      parseReviewBundle(
        reviewBundleArchive(bundle),
        metadataRoots("metadata/records"),
      ),
    ).toEqual(bundle);
  });

  it("requires exact object fields and rejects duplicate presentation identities", () => {
    const extra = { ...reviewBundle(), hidden: true };
    expect(() => parseReviewBundle(reviewBundleArchive(extra))).toThrow(
      "missing or unexpected fields",
    );

    const duplicate = reviewBundle();
    const second = duplicate.candidates[1];
    if (second === undefined) throw new Error("missing fixture candidate");
    second.friendly_id = duplicate.candidates[0]?.friendly_id ?? "";
    expect(() => parseReviewBundle(reviewBundleArchive(duplicate))).toThrow(
      "identities and paths must be unique",
    );
  });

  it("enforces the 225-candidate service bound independently of Markdown", () => {
    const bundle = reviewBundle();
    const template = bundle.candidates[0];
    if (template === undefined) throw new Error("missing fixture candidate");
    bundle.candidates = Array.from(
      { length: MAX_REVIEW_CANDIDATES + 1 },
      (_, index) => {
        const id = String(index).padStart(4, "0");
        const path = `site-specific/metadata/records/example/${id}.yaml`;
        return {
          ...template,
          claim_sha256: CLAIM_ONE,
          friendly_id: `DRI-${id}`,
          paths: [path],
          pid: `example:${id}`,
          record_path: path,
          source_record_id: `item:${id}`,
        };
      },
    );

    expect(() => parseReviewBundle(reviewBundleArchive(bundle))).toThrow(
      `1 to ${MAX_REVIEW_CANDIDATES} records`,
    );
  });

  it("requires one regular top-level review-bundle.json ZIP entry", () => {
    const payload = strToU8(JSON.stringify(reviewBundle()));
    expect(() =>
      parseReviewBundle(zipSync({ "nested/review-bundle.json": payload })),
    ).toThrow("regular top-level review-bundle.json");
    expect(() =>
      parseReviewBundle(
        zipSync({ "review-bundle.json": payload, "second.json": payload }),
      ),
    ).toThrow("exactly one ordinary entry");

    const symlink = reviewBundleArchive();
    const directory = centralDirectory(symlink);
    const data = new DataView(
      symlink.buffer,
      symlink.byteOffset,
      symlink.byteLength,
    );
    data.setUint16(directory + 4, (3 << 8) | 20, true);
    data.setUint32(directory + 38, (0o120777 << 16) >>> 0, true);
    expect(() => parseReviewBundle(symlink)).toThrow(
      "regular top-level review-bundle.json",
    );
  });

  it("rejects a declared uncompressed entry beyond the bundle bound", () => {
    const archive = reviewBundleArchive();
    const directory = centralDirectory(archive);
    new DataView(
      archive.buffer,
      archive.byteOffset,
      archive.byteLength,
    ).setUint32(directory + 24, MAX_REVIEW_BUNDLE_BYTES + 1, true);

    expect(() => parseReviewBundle(archive)).toThrow(
      "unsupported or too large",
    );
  });
});

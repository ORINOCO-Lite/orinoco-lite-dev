import { Store } from 'n3';

import { getRecordQuads, quadsToTTL, toCURIE } from '@/modules/utils';

export const REVIEW_BUNDLE_FORMAT = 'orinoco-shacl-review-bundle';
export const REVIEW_BUNDLE_VERSION = 2;

function requireString(value, label) {
    if (typeof value !== 'string' || !value.length) {
        throw new Error(`Record catalog has an invalid ${label}`);
    }
    return value;
}

export function validateRecordCatalog(catalog) {
    if (
        !catalog ||
        catalog.format !== 'orinoco-static-record-sources' ||
        catalog.version !== 2 ||
        !/^[0-9a-f]{40}$/.test(catalog.source_commit || '') ||
        !Array.isArray(catalog.records)
    ) {
        throw new Error('Static record catalog does not satisfy version 2');
    }

    const byPid = new Map();
    for (const record of catalog.records) {
        const pid = requireString(record?.pid, 'PID');
        if (byPid.has(pid)) {
            throw new Error(
                `Static record catalog contains duplicate PID ${pid}`
            );
        }
        requireString(record.schema_type, `${pid} schema type`);
        requireString(record.path, `${pid} source path`);
        requireString(record.rdf_turtle, `${pid} RDF`);
        if (!/^[0-9a-f]{64}$/.test(record.sha256 || '')) {
            throw new Error(
                `Static record catalog has an invalid ${pid} digest`
            );
        }
        byPid.set(pid, record);
    }
    return byPid;
}

export async function buildReviewBundle({
    catalog,
    selectedNodes,
    graph,
    prefixes,
}) {
    const catalogByPid = validateRecordCatalog(catalog);
    const selected = [...selectedNodes].sort((left, right) =>
        left.node_iri.localeCompare(right.node_iri)
    );
    if (!selected.length) {
        throw new Error('Select at least one edited record');
    }

    const records = [];
    for (const node of selected) {
        const pid = toCURIE(node.node_iri, prefixes);
        const source = catalogByPid.get(pid);
        if (!source) {
            throw new Error(
                `Edited record is not in the static catalog: ${pid}`
            );
        }
        const dataset = new Store();
        dataset.addQuads(getRecordQuads(node.node_iri, graph, true));
        const quads = dataset
            .getQuads(null, null, null, null)
            .sort((left, right) => left.id.localeCompare(right.id));
        if (!quads.length) {
            throw new Error(`Edited record has no RDF statements: ${pid}`);
        }
        const rdfTurtle = `${(await quadsToTTL(quads, prefixes)).trim()}\n`;
        records.push({
            pid,
            rdf_turtle: rdfTurtle,
            schema_type: source.schema_type,
            source_path: source.path,
            source_sha256: source.sha256,
        });
    }

    return {
        format: REVIEW_BUNDLE_FORMAT,
        records,
        source_commit: catalog.source_commit,
        version: REVIEW_BUNDLE_VERSION,
    };
}

export function reviewBundleFilename(records) {
    const label =
        records.length === 1 ? records[0].pid : `${records.length}-records`;
    const safe = label.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-|-$/g, '');
    return `orinoco-review-${safe || 'records'}.json`;
}

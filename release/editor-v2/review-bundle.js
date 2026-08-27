import { Store } from 'n3';

import { getRecordQuads, quadsToTTL, toCURIE } from '@/modules/utils';

export const REVIEW_BUNDLE_FORMAT = 'orinoco-shacl-review-bundle';
export const REVIEW_BUNDLE_VERSION = 2;
export const REVIEW_BUNDLE_EVENT = 'orinoco:review-bundle';
export const REVIEW_BUNDLE_MESSAGE_FORMAT =
    'orinoco-lite-shacl-bundle-message-v1';
export const REVIEW_PROPOSAL_READY_FORMAT =
    'orinoco-lite-shacl-proposal-ready-v1';

const GITHUB_REPOSITORY =
    /^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/;
const HANDOFF_TIMEOUT_MS = 10 * 60 * 1000;

export function dispatchReviewBundle(bundle, target = window) {
    return target.dispatchEvent(
        new CustomEvent(REVIEW_BUNDLE_EVENT, { detail: bundle })
    );
}

function reviewProposalCoordinates(value) {
    const repository = requireString(value?.repository, 'proposal repository');
    if (!GITHUB_REPOSITORY.test(repository) || repository.includes('..')) {
        throw new Error('Review proposal has an invalid GitHub repository');
    }
    const serviceOrigin = requireString(
        value?.service_origin,
        'proposal service origin'
    );
    let service;
    try {
        service = new URL(serviceOrigin);
    } catch {
        throw new Error('Review proposal has an invalid service origin');
    }
    const loopback =
        service.protocol === 'http:' &&
        ['127.0.0.1', 'localhost'].includes(service.hostname);
    if (
        (service.protocol !== 'https:' && !loopback) ||
        service.origin !== serviceOrigin ||
        service.pathname !== '/' ||
        service.search ||
        service.hash ||
        service.username ||
        service.password
    ) {
        throw new Error('Review proposal has an invalid service origin');
    }
    return { repository, serviceOrigin };
}

function editorOrigin(target) {
    const value = target.location?.origin;
    let origin;
    try {
        origin = new URL(value);
    } catch {
        throw new Error('The static editor has an invalid origin');
    }
    const loopback =
        origin.protocol === 'http:' &&
        ['127.0.0.1', 'localhost'].includes(origin.hostname);
    if (
        (origin.protocol !== 'https:' && !loopback) ||
        origin.origin !== value ||
        origin.pathname !== '/' ||
        origin.search ||
        origin.hash ||
        origin.username ||
        origin.password
    ) {
        throw new Error('The static editor has an invalid origin');
    }
    return value;
}

function handoffNonce(target) {
    const bytes = new Uint8Array(32);
    target.crypto.getRandomValues(bytes);
    return [...bytes]
        .map((value) => value.toString(16).padStart(2, '0'))
        .join('');
}

export function beginReviewBundleProposal(value, target = window) {
    const { repository, serviceOrigin } = reviewProposalCoordinates(value);
    const sourceOrigin = editorOrigin(target);
    const nonce = handoffNonce(target);
    const url = new URL('/edit/', serviceOrigin);
    url.searchParams.set('repository', repository);
    url.searchParams.set('editor_origin', sourceOrigin);
    url.searchParams.set('handoff_nonce', nonce);
    let popup;
    let bundle;
    let ready = false;
    let timeout;

    function dispose() {
        target.removeEventListener('message', receiveReady);
        if (timeout !== undefined) target.clearTimeout(timeout);
        bundle = undefined;
    }

    function sendIfReady() {
        if (!ready || bundle === undefined || popup?.closed) return;
        popup.postMessage(
            {
                bundle,
                format: REVIEW_BUNDLE_MESSAGE_FORMAT,
                handoff_nonce: nonce,
                repository,
            },
            serviceOrigin
        );
        dispose();
    }

    function receiveReady(event) {
        if (
            event.origin !== serviceOrigin ||
            event.source !== popup ||
            event.data?.format !== REVIEW_PROPOSAL_READY_FORMAT ||
            event.data?.handoff_nonce !== nonce ||
            event.data?.repository?.toLowerCase() !== repository.toLowerCase()
        ) {
            return;
        }
        ready = true;
        sendIfReady();
    }

    target.addEventListener('message', receiveReady);
    popup = target.open(
        url.toString(),
        `orinoco-lite-shacl-proposal-${nonce}`
    );
    if (!popup) {
        dispose();
        throw new Error('The GitHub proposal window was blocked');
    }
    timeout = target.setTimeout(dispose, HANDOFF_TIMEOUT_MS);
    return {
        cancel: dispose,
        deliver(reviewBundle) {
            bundle = reviewBundle;
            sendIfReady();
        },
    };
}

export function recordSubmissionLabel({
    classLabel,
    recordIri,
    recordLabel,
    prefixes,
}) {
    const pid = toCURIE(recordIri, prefixes);
    return [classLabel, recordLabel, pid, recordIri]
        .filter(
            (value, index, values) =>
                typeof value === 'string' &&
                value.length &&
                values.indexOf(value) === index
        )
        .join(': ');
}

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

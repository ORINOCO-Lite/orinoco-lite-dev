import { Parser, Store } from 'n3';
import { editorSubmission, openAuthentication, uploadSubmission } from './repository-auth.js';

import { getRecordQuads, quadsToTTL, toCURIE, toIRI } from '@/modules/utils';

export const REVIEW_BUNDLE_FORMAT = 'orinoco-shacl-review-bundle';
export const REVIEW_BUNDLE_VERSION = 3;
export const REVIEW_BUNDLE_EVENT = 'orinoco:review-bundle';
export const CURATION_INSTALL_URL =
    'https://github.com/apps/orinoco-lite-curation-review/installations/new';
export const CURATION_SETUP_URL =
    'https://github.com/ORINOCO-Lite/orinoco-lite-dev/blob/main/packages/curation-review-app/README.md#fix-github-authorization';

const GITHUB_REPOSITORY =
    /^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/;

function exactKeys(value, expected) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
        return false;
    }
    const observed = Object.keys(value).sort();
    const required = [...expected].sort();
    return (
        observed.length === required.length &&
        observed.every((key, index) => key === required[index])
    );
}

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
    return { repository, serviceOrigin, target: reviewProposalTarget(value) };
}

export function reviewProposalTarget(value) {
    if (value?.target === undefined) return { kind: 'standalone' };
    const target = value.target;
    if (
        !exactKeys(target, ['kind', 'pull_request']) ||
        target.kind !== 'pull_request' ||
        !Number.isSafeInteger(target.pull_request) ||
        target.pull_request < 1
    ) {
        throw new Error('Review proposal has an invalid pull-request target');
    }
    return {
        kind: 'pull_request',
        pull_request: target.pull_request,
    };
}

function setupUrl(value) {
    const candidate = value?.setup_url || CURATION_SETUP_URL;
    let url;
    try {
        url = new URL(candidate);
    } catch {
        throw new Error('Review proposal has an invalid setup URL');
    }
    if (
        url.protocol !== 'https:' ||
        url.origin !== 'https://github.com' ||
        url.username ||
        url.password ||
        url.search ||
        url.href !== candidate
    ) {
        throw new Error('Review proposal has an invalid setup URL');
    }
    return candidate;
}

function installUrl(value) {
    const candidate = value?.install_url || CURATION_INSTALL_URL;
    let url;
    try {
        url = new URL(candidate);
    } catch {
        throw new Error('Review proposal has an invalid install URL');
    }
    if (
        url.protocol !== 'https:' ||
        url.origin !== 'https://github.com' ||
        url.username ||
        url.password ||
        url.search ||
        url.hash ||
        !/^\/apps\/[A-Za-z0-9-]+\/installations\/new$/.test(url.pathname) ||
        url.href !== candidate
    ) {
        throw new Error('Review proposal has an invalid install URL');
    }
    return candidate;
}

export function curationSetupUrl(value) {
    return setupUrl(value);
}

export function curationInstallUrl(value) {
    return installUrl(value);
}

export function isSharedGithubPagesOrigin(target = window) {
    const hostname = String(target.location?.hostname || '')
        .toLowerCase()
        .replace(/\.+$/, '');
    return hostname === 'github.io' || hostname.endsWith('.github.io');
}

export function isFramedContext(target = window) {
    try {
        return target.top !== target.self;
    } catch {
        return true;
    }
}

export function beginReviewBundleProposal(
    value,
    target = window,
    { checkOnly = false } = {}
) {
    if (isFramedContext(target)) {
        throw new Error('Open the editor in its own tab to propose via GitHub.');
    }
    const { repository, serviceOrigin, target: proposalTarget } = reviewProposalCoordinates(value);
    const authentication = openAuthentication({
        repository, service_origin: serviceOrigin, kind: 'shacl',
    }, target);
    let delivered = false;
    return {
        cancel: () => authentication.cancel(),
        async deliver(proposal) {
            if (delivered) throw new Error('This submission was already delivered.');
            delivered = true;
            try {
                const source = checkOnly ? value.source_commit : proposal.bundle.source_commit;
                const access = await authentication.credentials(source);
                if (checkOnly) return { ready: true };
                // Convert Vue proxies to ordinary JSON before upload. The
                // bundle is sent directly to GitHub, never to authentication.
                const bundle = JSON.parse(JSON.stringify(proposal.bundle));
                const input = await editorSubmission(bundle, proposalTarget, access);
                return await uploadSubmission(input, access, authentication);
            } finally {
                await authentication.release().catch(() => authentication.cancel());
            }
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
        ![2, 3].includes(catalog.version) ||
        !/^[0-9a-f]{40}$/.test(catalog.source_commit || '') ||
        !Array.isArray(catalog.records)
    ) {
        throw new Error('Static record catalog does not satisfy version 2');
    }

    const byPid = new Map();
    if (
        catalog.version === 3 &&
        (typeof catalog.records_root !== 'string' ||
            !catalog.records_root ||
            catalog.records_root.startsWith('/') ||
            /[\\\u0000-\u001f\u007f]/.test(catalog.records_root) ||
            catalog.records_root
                .split('/')
                .some((part) => !part || part === '.' || part === '..') ||
            !Array.isArray(catalog.new_record_schema_types) ||
            catalog.new_record_schema_types.some(
                (type) =>
                    !/^[A-Za-z][A-Za-z0-9_-]*:[A-Za-z][A-Za-z0-9_]*$/.test(type)
            ))
    )
        throw new Error(
            'Static record catalog has invalid new record coordinates'
        );
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

async function newRecordSource(catalog, pid, schemaType) {
    if (
        catalog.version !== 3 ||
        !catalog.new_record_schema_types.includes(schemaType)
    ) {
        throw new Error(
            `New record schema type is not editable: ${schemaType}`
        );
    }
    const digest = await crypto.subtle.digest(
        'SHA-256',
        new TextEncoder().encode(pid)
    );
    const filename = Array.from(new Uint8Array(digest), (byte) =>
        byte.toString(16).padStart(2, '0')
    ).join('');
    return {
        path: `${catalog.records_root}/${schemaType.split(':')[1]}/${filename}.yaml`,
        schema_type: schemaType,
        sha256: null,
    };
}

async function reviewBundleRecords(bundle, catalogByPid, catalog) {
    if (
        !exactKeys(bundle, ['format', 'records', 'source_commit', 'version']) ||
        bundle.format !== REVIEW_BUNDLE_FORMAT ||
        ![2, 3].includes(bundle.version) ||
        bundle.source_commit !== catalog.source_commit ||
        !Array.isArray(bundle.records) ||
        !bundle.records.length ||
        bundle.records.length > 50
    ) {
        throw new Error('Review bundle does not match this deployed editor');
    }
    const pids = new Set();
    const paths = new Set();
    const records = [];
    for (const record of bundle.records) {
        if (
            !exactKeys(record, [
                'pid',
                'rdf_turtle',
                'schema_type',
                'source_path',
                'source_sha256',
            ]) ||
            typeof record.pid !== 'string' ||
            typeof record.rdf_turtle !== 'string' ||
            !record.rdf_turtle.trim() ||
            record.rdf_turtle.includes('\0') ||
            typeof record.schema_type !== 'string' ||
            typeof record.source_path !== 'string' ||
            (record.source_sha256 !== null &&
                !/^[0-9a-f]{64}$/.test(record.source_sha256)) ||
            (record.source_sha256 === null && bundle.version !== 3) ||
            pids.has(record.pid) ||
            paths.has(record.source_path)
        ) {
            throw new Error('Review bundle contains an invalid record');
        }
        let source = catalogByPid.get(record.pid);
        if (record.source_sha256 === null && !source) {
            source = await newRecordSource(
                catalog,
                record.pid,
                record.schema_type
            );
            if (catalog.records.some((entry) => entry.path === source.path)) {
                throw new Error(
                    `New record source path already exists: ${source.path}`
                );
            }
        }
        if (
            !source ||
            source.schema_type !== record.schema_type ||
            source.path !== record.source_path ||
            source.sha256 !== record.source_sha256
        ) {
            throw new Error(
                `Review bundle record does not match this deployment: ${record.pid}`
            );
        }
        pids.add(record.pid);
        paths.add(record.source_path);
        records.push(record);
    }
    return records;
}

export async function restoreReviewBundle({
    bundle,
    catalog,
    graph,
    prefixes,
}) {
    const catalogByPid = validateRecordCatalog(catalog);
    const records = await reviewBundleRecords(bundle, catalogByPid, catalog);
    const restored = records.map((record) => {
        const nodeIri = toIRI(record.pid, prefixes);
        const nodeShapeIri = toIRI(record.schema_type, prefixes);
        if (
            typeof nodeIri !== 'string' ||
            !nodeIri.includes(':') ||
            typeof nodeShapeIri !== 'string' ||
            !nodeShapeIri.includes(':')
        ) {
            throw new Error(
                `Review bundle uses an unknown prefix: ${record.pid}`
            );
        }
        let quads;
        try {
            quads = new Parser().parse(record.rdf_turtle);
        } catch {
            throw new Error(`Review bundle RDF is invalid: ${record.pid}`);
        }
        const imported = new Store(quads);
        const recordQuads = getRecordQuads(nodeIri, imported, true);
        if (
            !recordQuads.length ||
            recordQuads.length !== imported.size ||
            !recordQuads.some((quad) => quad.subject.value === nodeIri)
        ) {
            throw new Error(
                `Review bundle RDF does not describe its record: ${record.pid}`
            );
        }
        return {
            node_iri: nodeIri,
            nodeshape_iri: nodeShapeIri,
            quads: recordQuads,
        };
    });

    for (const record of restored) {
        for (const quad of getRecordQuads(record.node_iri, graph, true)) {
            graph.removeQuad(quad);
        }
        for (const quad of record.quads) graph.addQuad(quad);
    }
    return restored.map(({ node_iri, nodeshape_iri }) => ({
        node_iri,
        nodeshape_iri,
    }));
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
        let source = catalogByPid.get(pid);
        if (!source) {
            source = await newRecordSource(
                catalog,
                pid,
                toCURIE(node.nodeshape_iri, prefixes)
            );
            if (
                catalog.records.some((entry) => entry.path === source.path) ||
                records.some((entry) => entry.source_path === source.path)
            ) {
                throw new Error(
                    `New record source path already exists: ${source.path}`
                );
            }
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
        version: catalog.version === 2 ? 2 : REVIEW_BUNDLE_VERSION,
    };
}

export function reviewBundleFilename(records) {
    const label =
        records.length === 1 ? records[0].pid : `${records.length}-records`;
    const safe = label.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-|-$/g, '');
    return `orinoco-review-${safe || 'records'}.json`;
}

// HTTP status alone cannot distinguish policy, identity, installation, or trust failures.
export function proposalFailureGuidance(code) {
    if (code === 'installation_access_required') return 'installation';
    if (['authentication_required', 'shacl_grant_required'].includes(code))
        return 'signin';
    if (
        ['curator_permission_required', 'metadata_access_required'].includes(
            code
        )
    )
        return 'permission';
    return 'other';
}

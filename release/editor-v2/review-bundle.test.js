import { describe, expect, it, vi } from 'vitest';
import { DataFactory, Store, Writer } from 'n3';

vi.mock('@/modules/utils', () => ({
    getRecordQuads: (iri, graph) => graph.getQuads(iri, null, null, null),
    quadsToTTL: (quads, prefixes) =>
        new Promise((resolve, reject) => {
            const writer = new Writer({ prefixes });
            writer.addQuads(quads);
            writer.end((error, result) =>
                error ? reject(error) : resolve(result)
            );
        }),
    toCURIE: (iri, prefixes) => {
        for (const [prefix, namespace] of Object.entries(prefixes)) {
            if (iri.startsWith(namespace))
                return `${prefix}:${iri.slice(namespace.length)}`;
        }
        return iri;
    },
}));

const {
    buildReviewBundle,
    beginReviewBundleProposal,
    dispatchReviewBundle,
    isFramedContext,
    isSharedGithubPagesOrigin,
    recordSubmissionLabel,
    REVIEW_BUNDLE_EVENT,
    REVIEW_PROPOSAL_MESSAGE_FORMAT,
    REVIEW_PROPOSAL_READY_FORMAT,
    REVIEW_PROPOSAL_RESULT_FORMAT,
    REVIEW_PROPOSAL_STARTED_FORMAT,
    reviewBundleFilename,
    validateRecordCatalog,
} = await import('../src/modules/review-bundle');

const { namedNode, literal, quad } = DataFactory;
const PID = 'xyzrins:persons/example';
const IRI = 'https://example.test/r/persons/example';
const SOURCE_COMMIT = 'a'.repeat(40);
const SOURCE_SHA256 = 'b'.repeat(64);
const catalog = {
    format: 'orinoco-static-record-sources',
    records: [
        {
            path: 'metadata/records/XYZPerson/example.yaml',
            pid: PID,
            rdf_turtle: '<https://example.test/r/persons/example> <x:p> "x" .\n',
            schema_type: 'xyzri:XYZPerson',
            sha256: SOURCE_SHA256,
        },
    ],
    source_commit: SOURCE_COMMIT,
    version: 2,
};

describe('Orinoco review bundles', () => {
    it('names submission controls with the canonical catalog PID', () => {
        expect(
            recordSubmissionLabel({
                classLabel: 'Person',
                recordIri: IRI,
                recordLabel: 'Example person',
                prefixes: { xyzrins: 'https://example.test/r/' },
            })
        ).toBe(
            'Person: Example person: xyzrins:persons/example: ' + IRI
        );
    });

    it('binds selected RDF to flattened immutable source coordinates', async () => {
        const graph = new Store([
            quad(IRI, namedNode('http://www.w3.org/2000/01/rdf-schema#label'), literal('Changed label')),
        ]);
        const bundle = await buildReviewBundle({
            catalog,
            graph,
            prefixes: {
                rdfs: 'http://www.w3.org/2000/01/rdf-schema#',
                xyzrins: 'https://example.test/r/',
            },
            selectedNodes: [{ node_iri: IRI }],
        });
        expect(bundle).toMatchObject({
            format: 'orinoco-shacl-review-bundle',
            source_commit: SOURCE_COMMIT,
            version: 2,
        });
        expect(bundle.records[0]).toMatchObject({
            pid: PID,
            schema_type: 'xyzri:XYZPerson',
            source_path: 'metadata/records/XYZPerson/example.yaml',
            source_sha256: SOURCE_SHA256,
        });
        expect(bundle.records[0].rdf_turtle).toContain('Changed label');
    });

    it('exposes the exact generated bundle through a browser event', async () => {
        const graph = new Store([
            quad(IRI, namedNode('http://www.w3.org/2000/01/rdf-schema#label'), literal('Changed label')),
        ]);
        const bundle = await buildReviewBundle({
            catalog,
            graph,
            prefixes: {
                rdfs: 'http://www.w3.org/2000/01/rdf-schema#',
                xyzrins: 'https://example.test/r/',
            },
            selectedNodes: [{ node_iri: IRI }],
        });
        let observed;
        window.addEventListener(
            REVIEW_BUNDLE_EVENT,
            (event) => {
                observed = event.detail;
            },
            { once: true }
        );

        expect(dispatchReviewBundle(bundle)).toBe(true);
        expect(observed).toBe(bundle);
    });

    it('sends a confirmed proposal only to the exact transport popup', async () => {
        const listeners = new Map();
        const popup = { closed: false, postMessage: vi.fn() };
        const nonce = '0a'.repeat(32);
        const target = {
            addEventListener: vi.fn((type, listener) =>
                listeners.set(type, listener)
            ),
            clearTimeout: vi.fn(),
            crypto: {
                getRandomValues: vi.fn((value) => value.fill(10)),
            },
            location: {
                hostname: 'site.example.test',
                origin: 'https://site.example.test',
            },
            open: vi.fn(() => popup),
            removeEventListener: vi.fn(),
            clearInterval: vi.fn(),
            setTimeout: vi.fn(() => 17),
            setInterval: vi.fn(() => 18),
        };
        const proposal = {
            acknowledge_public_data: true,
            bundle: {
                format: 'orinoco-shacl-review-bundle',
                records: [],
                source_commit: SOURCE_COMMIT,
                version: 2,
            },
            format: 'orinoco-lite-shacl-proposal-v1',
            repository: 'ORINOCO-Lite/example-site',
            target: { kind: 'standalone' },
        };
        const handoff = beginReviewBundleProposal(
            {
                repository: 'ORINOCO-Lite/example-site',
                service_origin: 'https://review.example.test',
            },
            target
        );
        expect(target.open).toHaveBeenCalledWith(
            'https://review.example.test/api/transport?kind=shacl&repository=ORINOCO-Lite%2Fexample-site&editor_origin=https%3A%2F%2Fsite.example.test&handoff_nonce=' +
                nonce,
            `orinoco-lite-shacl-proposal-${nonce}`
        );
        const delivered = handoff.deliver(proposal);
        const receive = listeners.get('message');
        receive({
            data: {
                format: REVIEW_PROPOSAL_READY_FORMAT,
                handoff_nonce: nonce,
                repository: 'ORINOCO-Lite/example-site',
            },
            origin: 'https://evil.example',
            source: popup,
        });
        expect(popup.postMessage).not.toHaveBeenCalled();
        receive({
            data: {
                format: REVIEW_PROPOSAL_READY_FORMAT,
                handoff_nonce: '0b'.repeat(32),
                repository: 'ORINOCO-Lite/example-site',
            },
            origin: 'https://review.example.test',
            source: popup,
        });
        expect(popup.postMessage).not.toHaveBeenCalled();
        receive({
            data: {
                format: REVIEW_PROPOSAL_READY_FORMAT,
                handoff_nonce: nonce,
                repository: 'ORINOCO-Lite/example-site',
            },
            origin: 'https://review.example.test',
            source: popup,
        });
        expect(popup.postMessage).toHaveBeenCalledWith(
            {
                format: REVIEW_PROPOSAL_MESSAGE_FORMAT,
                handoff_nonce: nonce,
                proposal,
                repository: 'ORINOCO-Lite/example-site',
            },
            'https://review.example.test'
        );
        receive({
            data: {
                format: REVIEW_PROPOSAL_STARTED_FORMAT,
                handoff_nonce: nonce,
                repository: 'ORINOCO-Lite/example-site',
            },
            origin: 'https://review.example.test',
            source: popup,
        });
        const result = {
            commit_sha: 'c'.repeat(40),
            commit_url:
                'https://github.com/ORINOCO-Lite/example-site/commit/' +
                'c'.repeat(40),
            pull_request: 42,
            pull_request_url:
                'https://github.com/ORINOCO-Lite/example-site/pull/42',
        };
        receive({
            data: {
                error: null,
                format: REVIEW_PROPOSAL_RESULT_FORMAT,
                handoff_nonce: nonce,
                repository: 'ORINOCO-Lite/example-site',
                result,
                retry_safe: false,
            },
            origin: 'https://review.example.test',
            source: popup,
        });
        await expect(delivered).resolves.toBe(result);
        expect(target.removeEventListener).toHaveBeenCalledWith(
            'message',
            receive
        );
        expect(target.clearTimeout).toHaveBeenCalledWith(17);
        expect(target.clearInterval).toHaveBeenCalledWith(18);
    });

    it('distinguishes retry-safe failures from uncertain post-start results', async () => {
        async function runFailure(retrySafe) {
            const listeners = new Map();
            const popup = { closed: false, postMessage: vi.fn() };
            const target = {
                addEventListener: (type, listener) =>
                    listeners.set(type, listener),
                clearInterval: vi.fn(),
                clearTimeout: vi.fn(),
                crypto: {
                    getRandomValues: (value) => value.fill(10),
                },
                location: {
                    hostname: 'site.example.test',
                    origin: 'https://site.example.test',
                },
                open: () => popup,
                removeEventListener: vi.fn(),
                setInterval: () => 18,
                setTimeout: () => 17,
            };
            const handoff = beginReviewBundleProposal(
                {
                    repository: 'ORINOCO-Lite/example-site',
                    service_origin: 'https://review.example.test',
                },
                target
            );
            const delivered = handoff.deliver({
                repository: 'ORINOCO-Lite/example-site',
            });
            const receive = listeners.get('message');
            for (const format of [
                REVIEW_PROPOSAL_READY_FORMAT,
                REVIEW_PROPOSAL_STARTED_FORMAT,
            ]) {
                receive({
                    data: {
                        format,
                        handoff_nonce: '0a'.repeat(32),
                        repository: 'ORINOCO-Lite/example-site',
                    },
                    origin: 'https://review.example.test',
                    source: popup,
                });
            }
            receive({
                data: {
                    error: 'GitHub did not return a complete result.',
                    format: REVIEW_PROPOSAL_RESULT_FORMAT,
                    handoff_nonce: '0a'.repeat(32),
                    repository: 'ORINOCO-Lite/example-site',
                    result: null,
                    retry_safe: retrySafe,
                },
                origin: 'https://review.example.test',
                source: popup,
            });
            return delivered;
        }

        await expect(runFailure(true)).rejects.toThrow(
            'GitHub did not return a complete result.'
        );
        await expect(runFailure(false)).rejects.toThrow(
            /result is uncertain.*before retrying/
        );
    });

    it('recognizes only the exact shared GitHub Pages hostname boundary', () => {
        for (const [hostname, expected] of [
            ['github.io', true],
            ['owner.github.io', true],
            ['OWNER.GITHUB.IO', true],
            ['OWNER.GITHUB.IO.', true],
            ['Owner.GitHub.Io...', true],
            ['example.github.io.attacker.test', false],
            ['example.github.io.attacker.test.', false],
            ['notgithub.io', false],
            ['curation.example.org', false],
        ]) {
            expect(
                isSharedGithubPagesOrigin({ location: { hostname } })
            ).toBe(expected);
        }
    });

    it('rejects unsafe proposal coordinates before opening a window', () => {
        for (const proposal of [
            {
                repository: 'not-a-repository',
                service_origin: 'https://review.example.test',
            },
            {
                repository: 'ORINOCO-Lite/example-site',
                service_origin: 'http://review.example.test',
            },
            {
                repository: 'ORINOCO-Lite/example-site',
                service_origin: 'https://review.example.test/edit/',
            },
        ]) {
            expect(() => beginReviewBundleProposal(proposal)).toThrow(
                /invalid/
            );
        }
    });

    it('refuses direct GitHub proposals in framed contexts', () => {
        const proposal = {
            repository: 'ORINOCO-Lite/example-site',
            service_origin: 'https://review.example.test',
        };
        const open = vi.fn();
        const framed = {
            open,
            self: {},
            top: {},
        };

        expect(isFramedContext(framed)).toBe(true);
        expect(() => beginReviewBundleProposal(proposal, framed)).toThrow(
            'Direct GitHub proposal is unavailable while the editor is embedded. Download the review bundle instead.'
        );
        expect(open).not.toHaveBeenCalled();
        expect(isFramedContext({ self: window, top: window })).toBe(false);

        const inaccessible = { self: window };
        Object.defineProperty(inaccessible, 'top', {
            get() {
                throw new Error('cross-origin frame');
            },
        });
        expect(isFramedContext(inaccessible)).toBe(true);
    });

    it('rejects old catalogs and produces deterministic filenames', () => {
        expect(() => validateRecordCatalog({ ...catalog, version: 1 })).toThrow(
            /version 2/
        );
        expect(reviewBundleFilename([{ pid: PID }])).toBe(
            'orinoco-review-xyzrins-persons-example.json'
        );
    });
});

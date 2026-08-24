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
    dispatchReviewBundle,
    recordSubmissionLabel,
    REVIEW_BUNDLE_EVENT,
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

    it('rejects old catalogs and produces deterministic filenames', () => {
        expect(() => validateRecordCatalog({ ...catalog, version: 1 })).toThrow(
            /version 2/
        );
        expect(reviewBundleFilename([{ pid: PID }])).toBe(
            'orinoco-review-xyzrins-persons-example.json'
        );
    });
});

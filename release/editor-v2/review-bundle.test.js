import { describe, expect, it, vi } from 'vitest';
import { DataFactory, Store, Writer } from 'n3';

const authMocks = vi.hoisted(() => ({
    openAuthentication: vi.fn(), uploadSubmission: vi.fn(),
    editorSubmission: vi.fn(async (bundle, target) => ({ operation: 'shacl', bundle, target })),
}));
vi.mock('../src/modules/repository-auth.js', () => authMocks);

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
    toIRI: (value, prefixes) => {
        const [prefix, suffix] = value.split(':', 2);
        return prefixes[prefix] ? `${prefixes[prefix]}${suffix}` : value;
    },
}));

const {
    proposalFailureGuidance,
    buildReviewBundle,
    beginReviewBundleProposal,
    curationInstallUrl,
    curationSetupUrl,
    dispatchReviewBundle,
    isFramedContext,
    isSharedGithubPagesOrigin,
    recordSubmissionLabel,
    restoreReviewBundle,
    reviewProposalTarget,
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
            rdf_turtle:
                '<https://example.test/r/persons/example> <x:p> "x" .\n',
            schema_type: 'xyzri:XYZPerson',
            sha256: SOURCE_SHA256,
        },
    ],
    source_commit: SOURCE_COMMIT,
    version: 2,
};

const creationCatalog = {
    ...catalog,
    version: 3,
    records_root: 'metadata/records',
    new_record_schema_types: ['xyzri:XYZPerson'],
};

describe('Orinoco review bundles', () => {
    it('downloads and restores a new record with an absent-source precondition', async () => {
        const iri = 'https://example.test/r/persons/new';
        const prefixes = {
            xyzri: 'https://example.test/s/',
            xyzrins: 'https://example.test/r/',
        };
        const graph = new Store([
            quad(
                namedNode(iri),
                namedNode('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'),
                namedNode('https://example.test/s/XYZPerson')
            ),
            quad(
                namedNode(iri),
                namedNode('http://www.w3.org/2000/01/rdf-schema#label'),
                literal('New person')
            ),
        ]);
        const bundle = await buildReviewBundle({
            catalog: creationCatalog,
            graph,
            prefixes,
            selectedNodes: [
                {
                    node_iri: iri,
                    nodeshape_iri: 'https://example.test/s/XYZPerson',
                },
            ],
        });
        expect(bundle.version).toBe(3);
        expect(bundle.records[0].source_sha256).toBeNull();
        expect(bundle.records[0].source_path).toMatch(
            /^metadata\/records\/XYZPerson\/[a-f0-9]{64}\.yaml$/
        );
        const restoredGraph = new Store();
        await restoreReviewBundle({
            bundle,
            catalog: creationCatalog,
            graph: restoredGraph,
            prefixes,
        });
        expect(restoredGraph.size).toBe(2);
        bundle.records[0].source_path =
            'metadata/records/XYZPerson/arbitrary.yaml';
        await expect(
            restoreReviewBundle({
                bundle,
                catalog: creationCatalog,
                graph: restoredGraph,
                prefixes,
            })
        ).rejects.toThrow('does not match this deployment');
        expect(restoredGraph.size).toBe(2);
        await expect(
            buildReviewBundle({
                catalog: creationCatalog,
                graph,
                prefixes,
                selectedNodes: [
                    {
                        node_iri: iri,
                        nodeshape_iri: 'https://example.test/s/XYZAgentRole',
                    },
                ],
            })
        ).rejects.toThrow('not editable');
    });
    it('identifies the pull request without a current-head permission check', () => {
        const target = {
            kind: 'pull_request',
            pull_request: 42,
        };
        expect(reviewProposalTarget({ target: new Proxy(target, {}) })).toEqual(
            target
        );
        expect(reviewProposalTarget({})).toEqual({ kind: 'standalone' });
        expect(() =>
            reviewProposalTarget({ target: { ...target, pull_request: 0 } })
        ).toThrow('invalid pull-request target');
    });

    it('names submission controls with the canonical catalog PID', () => {
        expect(
            recordSubmissionLabel({
                classLabel: 'Person',
                recordIri: IRI,
                recordLabel: 'Example person',
                prefixes: { xyzrins: 'https://example.test/r/' },
            })
        ).toBe('Person: Example person: xyzrins:persons/example: ' + IRI);
    });

    it('binds selected RDF to flattened immutable source coordinates', async () => {
        const graph = new Store([
            quad(
                IRI,
                namedNode('http://www.w3.org/2000/01/rdf-schema#label'),
                literal('Changed label')
            ),
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
            quad(
                IRI,
                namedNode('http://www.w3.org/2000/01/rdf-schema#label'),
                literal('Changed label')
            ),
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

    it('restores a downloaded bundle into the matching deployed editor', async () => {
        const graph = new Store([
            quad(
                IRI,
                namedNode('http://www.w3.org/2000/01/rdf-schema#label'),
                literal('Original label')
            ),
        ]);
        const bundle = {
            format: 'orinoco-shacl-review-bundle',
            records: [
                {
                    pid: PID,
                    rdf_turtle:
                        `<${IRI}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ` +
                        '<https://example.test/s/XYZPerson> ;\n' +
                        '  <http://www.w3.org/2000/01/rdf-schema#label> "Restored label" .\n',
                    schema_type: 'xyzri:XYZPerson',
                    source_path: catalog.records[0].path,
                    source_sha256: SOURCE_SHA256,
                },
            ],
            source_commit: SOURCE_COMMIT,
            version: 2,
        };

        expect(
            await restoreReviewBundle({
                bundle,
                catalog,
                graph,
                prefixes: {
                    xyzri: 'https://example.test/s/',
                    xyzrins: 'https://example.test/r/',
                },
            })
        ).toEqual([
            {
                node_iri: IRI,
                nodeshape_iri: 'https://example.test/s/XYZPerson',
            },
        ]);
        expect(graph.getQuads(IRI, null, null, null)).toHaveLength(2);
        expect(
            graph.getQuads(
                IRI,
                'http://www.w3.org/2000/01/rdf-schema#label',
                null,
                null
            )[0].object.value
        ).toBe('Restored label');
    });

    it('rejects a bundle from a different deployment before changing data', async () => {
        const original = quad(
            IRI,
            namedNode('http://www.w3.org/2000/01/rdf-schema#label'),
            literal('Original label')
        );
        const graph = new Store([original]);
        await expect(
            restoreReviewBundle({
                bundle: {
                    format: 'orinoco-shacl-review-bundle',
                    records: [],
                    source_commit: 'c'.repeat(40),
                    version: 2,
                },
                catalog,
                graph,
                prefixes: {},
            })
        ).rejects.toThrow('does not match this deployed editor');
        expect(graph.has(original)).toBe(true);
    });

    it('uploads the bundle directly and releases browser credentials', async () => {
        const access = { scope: 'fixture' };
        const channel = { credentials: vi.fn(async () => access), release: vi.fn(async () => {}), cancel: vi.fn() };
        authMocks.openAuthentication.mockReturnValue(channel);
        authMocks.uploadSubmission.mockResolvedValue({ workflow_url: 'https://github.com/owner/repo/actions' });
        const handoff = beginReviewBundleProposal({
            repository: 'owner/repo', service_origin: 'https://auth.example',
        });
        const bundle = new Proxy({ source_commit: SOURCE_COMMIT, records: [] }, {});
        const result = await handoff.deliver({ bundle });
        expect(channel.credentials).toHaveBeenCalledWith(SOURCE_COMMIT);
        expect(authMocks.uploadSubmission).toHaveBeenLastCalledWith({
            operation: 'shacl', bundle: { source_commit: SOURCE_COMMIT, records: [] }, target: { kind: 'standalone' },
        }, access, channel);
        expect(result.workflow_url).toContain('/actions');
        expect(channel.release).toHaveBeenCalledOnce();
    });

    it('checks access without uploading any input', async () => {
        const channel = { credentials: vi.fn(async () => ({})), release: vi.fn(async () => {}), cancel: vi.fn() };
        authMocks.openAuthentication.mockReturnValue(channel);
        authMocks.uploadSubmission.mockClear();
        const handoff = beginReviewBundleProposal({
            repository: 'owner/repo', service_origin: 'https://auth.example', source_commit: SOURCE_COMMIT,
        }, window, { checkOnly: true });
        await expect(handoff.deliver(null)).resolves.toEqual({ ready: true });
        expect(authMocks.uploadSubmission).not.toHaveBeenCalled();
        expect(channel.release).toHaveBeenCalledOnce();
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
            expect(isSharedGithubPagesOrigin({ location: { hostname } })).toBe(
                expected
            );
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

    it('provides setup instructions for GitHub authorization failures', () => {
        expect(curationSetupUrl({})).toContain(
            'packages/curation-review-app/README.md#fix-github-authorization'
        );
        expect(curationInstallUrl({})).toBe(
            'https://github.com/apps/orinoco-lite-curation-review/installations/new'
        );
        expect(
            curationSetupUrl({
                setup_url:
                    'https://github.com/example/site/blob/main/README.md',
            })
        ).toBe('https://github.com/example/site/blob/main/README.md');
        expect(() =>
            curationSetupUrl({ setup_url: 'https://example.test/setup' })
        ).toThrow(/setup URL/);
        expect(() =>
            curationInstallUrl({
                install_url: 'https://github.com/settings/apps/new',
            })
        ).toThrow(/install URL/);
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
            'Open the editor in its own tab to propose via GitHub.'
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

describe('proposal failure guidance', () => {
    it.each([
        ['installation_access_required', 'installation'],
        ['authentication_required', 'signin'],
        ['curator_permission_required', 'permission'],
        ['github_forbidden', 'other'],
        ['github_not_found', 'other'],
        ['invalid_origin', 'other'],
        ['metadata_handoff_incomplete', 'other'],
    ])(
        'reports %s without inferring installation from HTTP status',
        (code, expected) => {
            expect(proposalFailureGuidance(code)).toBe(expected);
        }
    );
});

import { execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

import { startStaticServer } from './static-server.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const PAGES_ROOT = path.join(
  ROOT,
  'build/pages-preview',
);
const PERSON_PID = 'xyzrins:persons/yaroslav-halchenko';
const execFileAsync = promisify(execFile);

test('project-path editor changes a record and downloads without a backend write', async ({
  context,
  page,
}) => {
  await context.addInitScript(() => {
    sessionStorage.setItem('serviceToken', 'inherited-static-token');
  });
  const fixture = await startStaticServer({ pages: PAGES_ROOT }, 'pages');
  const mutationRequests = [];
  context.on('request', (request) => {
    if (!['GET', 'HEAD'].includes(request.method())) mutationRequests.push(request);
  });
  try {
    await page.goto(`${fixture.origin}/orinoco-lite-dev/persons/yaroslav-halchenko/`);
    const publishedEdit = new URL(
      await page.getByRole('link', { name: 'Edit this record' }).getAttribute('href'),
    );
    const editorURL = new URL('/orinoco-lite-dev/edit/', fixture.origin);
    editorURL.search = publishedEdit.search;
    editorURL.searchParams.set('token', 'query-static-token');
    await page.goto(editorURL.href);

    await expect(page.getByText('Person', { exact: true }).first()).toBeVisible();
    expect(new URL(page.url()).searchParams.has('token')).toBe(false);
    const givenNameRow = page.locator('.main-row').filter({
      has: page.locator('.row-label', { hasText: /Given name/i }),
    });
    const givenName = givenNameRow.locator('input').first();
    await expect(givenName).toHaveValue('Yaroslav');
    await givenName.fill('Yaroslav Browser Review');
    await page.getByRole('button', { name: 'Save', exact: true }).click();

    await page.locator('button:has(.mdi-download)').first().click();
    const submission = page.locator('#submitcomp');
    await expect(
      submission.getByRole('checkbox', { name: /Yaroslav/ }),
    ).toBeChecked();
    const downloadPromise = page.waitForEvent('download');
    await submission
      .getByRole('button', { name: 'Download review bundle', exact: true })
      .click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(
      'con-review-xyzrins-persons-yaroslav-halchenko.json',
    );
    const downloaded = await download.path();
    const bundle = JSON.parse(await readFile(downloaded, 'utf8'));
    expect(bundle.format).toBe('con-shacl-review-bundle');
    expect(bundle.version).toBe(1);
    expect(bundle.site_commit).toMatch(/^[0-9a-f]{40}$/);
    expect(bundle.records).toHaveLength(1);
    expect(bundle.records[0]).toMatchObject({
      pid: PERSON_PID,
      schema_type: 'xyzri:XYZPerson',
      source_path:
        'profiles/con/metadata/records/XYZPerson/yaroslav-halchenko.yaml',
    });
    expect(bundle.records[0].source_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(bundle.records[0].rdf_turtle).toContain('Yaroslav Browser Review');

    const dryRun = await execFileAsync(
      'python3',
      [path.join(ROOT, 'tools/apply_editor_bundle.py'), downloaded],
      { cwd: ROOT, maxBuffer: 10 * 1024 * 1024 },
    );
    expect(dryRun.stdout).toContain(
      'b/profiles/con/metadata/records/XYZPerson/yaroslav-halchenko.yaml',
    );
    expect(dryRun.stdout).toContain('Yaroslav Browser Review');
    expect(dryRun.stdout).toContain('Dry run only');

    expect(mutationRequests).toEqual([]);
    expect(fixture.requests.every(({ method }) => ['GET', 'HEAD'].includes(method))).toBe(
      true,
    );
    expect(
      await page.evaluate(() => ({
        local: Object.keys(localStorage),
        session: Object.keys(sessionStorage),
      })),
    ).toEqual({ local: [], session: [] });
  } finally {
    await fixture.close();
  }
});

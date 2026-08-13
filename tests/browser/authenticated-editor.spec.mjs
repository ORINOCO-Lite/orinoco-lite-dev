import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

import {
  cleanupProbe,
  loadEditorToken,
  loadProbeRecord,
  PROBE_PID,
  readProbeBoundaries,
  seedProbe,
} from './dump-things.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const PERSON_URL = 'http://127.0.0.1:8767/persons/yaroslav-halchenko/';

test.use({ trace: 'off', screenshot: 'off', video: 'off' });

test('an authenticated SHACL Vue edit reaches only the CON incoming boundary', async ({
  context,
  page,
}) => {
  const probe = await loadProbeRecord(ROOT);
  await cleanupProbe(ROOT);
  try {
    await seedProbe(ROOT, probe);
    await page.goto(PERSON_URL);
    const originalHref = await page
      .getByRole('link', { name: 'Edit this record' })
      .getAttribute('href');
    const editorURL = new URL(originalHref);
    editorURL.searchParams.set('pid', PROBE_PID);

    const editorToken = await loadEditorToken(ROOT);
    const editor = await context.newPage();
    await editor.addInitScript((token) => {
      sessionStorage.setItem('serviceToken', token);
    }, editorToken);

    let authenticatedPost;
    editor.on('request', async (request) => {
      const url = new URL(request.url());
      if (
        request.method() === 'POST'
        && url.pathname === '/con-protected/record/XYZPerson'
      ) {
        authenticatedPost = request;
      }
    });
    await editor.goto(editorURL.href);
    await expect(editor.getByText('Person', { exact: true }).first()).toBeVisible();

    const givenNameRow = editor.locator('.main-row').filter({
      has: editor.locator('.row-label', { hasText: /Given name/i }),
    });
    const givenName = givenNameRow.locator('input').first();
    await expect(givenName).toHaveValue('Playwright');
    await givenName.fill('Browser-tested');
    await editor.getByRole('button', { name: 'Save', exact: true }).click();

    await editor.locator('button:has(.mdi-cloud-upload)').click();
    const submission = editor.locator('#submitcomp');
    await expect(
      submission.getByRole('checkbox', { name: /Playwright Write Probe/ }),
    ).toBeChecked();
    await submission.getByRole('button', { name: 'Submit', exact: true }).click();
    await expect(
      submission.getByText('Your metadata submission was successful!', { exact: true }),
    ).toBeVisible();

    expect(authenticatedPost).toBeDefined();
    const postURL = new URL(authenticatedPost.url());
    expect(postURL.pathname).toBe('/con-protected/record/XYZPerson');
    expect(postURL.searchParams.get('format')).toBe('ttl');
    const postHeaders = await authenticatedPost.allHeaders();
    expect(Boolean(postHeaders['x-dumpthings-token'])).toBe(true);
    expect(postHeaders['content-type']).toContain('text/turtle');

    const boundaries = await readProbeBoundaries(ROOT);
    expect(boundaries['con-protected'].curated.given_name).toBe('Playwright');
    expect(boundaries['con-protected']['incoming/local-editor'].given_name).toBe(
      'Browser-tested',
    );
    for (const [collection, areas] of Object.entries(boundaries)) {
      if (collection === 'con-protected') {
        continue;
      }
      expect(areas.curated).toBeNull();
      expect(areas['incoming/local-editor']).toBeNull();
    }
  } finally {
    await cleanupProbe(ROOT);
  }
});

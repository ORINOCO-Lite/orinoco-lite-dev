import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

import { startStaticServer } from './static-server.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const EXPECTED_CON_PIDS = new Set([
  'ror:04tfhh831',
  'xyzrins:.',
  'xyzrins:instruments/datalad',
  'xyzrins:persons/yaroslav-halchenko',
  'xyzrins:projects/datalad',
  'xyzrins:publications/datalad-joss-2021',
]);

function graphResponse(page) {
  return page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.endsWith('/graph.json');
  });
}

test(
  'same-origin upstream cache cannot contaminate the CON graph',
  async ({ page }) => {
    const fixture = await startStaticServer(
      {
        upstream: path.join(ROOT, 'build/upstream-local'),
        con: path.join(ROOT, 'build/con-site'),
      },
      'upstream',
    );
    try {
      const firstGraph = graphResponse(page);
      await page.goto(`${fixture.origin}/`);
      const upstreamResponse = await firstGraph;
      const upstreamURL = new URL(upstreamResponse.url());
      const upstream = await upstreamResponse.json();
      expect(upstreamURL.searchParams.get('v')).toMatch(/^[0-9a-f]{64}$/);
      expect(upstream.nodes.length).toBeGreaterThan(100);
      expect(upstream.nodes.some((node) => node.label === 'PsyInf')).toBe(true);
      await expect(page.locator('#sigma-container canvas').first()).toBeVisible();

      fixture.use('con');
      const secondGraph = graphResponse(page);
      await page.reload();
      const conResponse = await secondGraph;
      const conURL = new URL(conResponse.url());
      const con = await conResponse.json();
      expect(conURL.searchParams.get('v')).toMatch(/^[0-9a-f]{64}$/);
      expect(conURL.href).not.toBe(upstreamURL.href);
      expect(new Set(con.nodes.map((node) => node.id))).toEqual(EXPECTED_CON_PIDS);
      expect(con.edges).toHaveLength(7);
      expect(con.nodes.map((node) => node.label)).not.toEqual(
        expect.arrayContaining(['PsyInf', 'FZJ', 'M.Hanke']),
      );
      await expect(
        page.getByRole('heading', { name: 'Center for Open Neuroscience' }),
      ).toBeVisible();
      await expect(page.locator('#sigma-container canvas').first()).toBeVisible();

      const scriptSource = await page
        .locator('script[src*="graph.js"]')
        .first()
        .getAttribute('src');
      expect(new URL(scriptSource, fixture.origin).searchParams.get('v')).toBe(
        conURL.searchParams.get('v'),
      );
    } finally {
      await fixture.close();
    }
  },
);

test('project-path graph resources and routes resolve', async ({ page }) => {
  const fixture = await startStaticServer(
    { con: path.join(ROOT, 'build/con-site-project') },
    'con',
    { mountPath: '/clean-migration/' },
  );
  try {
    const graph = graphResponse(page);
    await page.goto(`${fixture.origin}/clean-migration/`);
    const response = await graph;
    expect(new URL(response.url()).pathname).toBe('/clean-migration/graph.json');
    expect(new URL(response.url()).searchParams.get('v')).toMatch(
      /^[0-9a-f]{64}$/,
    );
    const personHref = await page
      .getByRole('link', { name: 'Yaroslav Halchenko' })
      .first()
      .getAttribute('href');
    const personPath = new URL(personHref).pathname;
    expect(personPath).toBe('/clean-migration/persons/yaroslav-halchenko/');
    await page.goto(`${fixture.origin}${personPath}`);
    await expect(page).toHaveURL(/\/clean-migration\/persons\/yaroslav-halchenko\/$/);
    await expect(
      page.getByRole('heading', { name: 'Yaroslav Halchenko' }),
    ).toBeVisible();
  } finally {
    await fixture.close();
  }
});

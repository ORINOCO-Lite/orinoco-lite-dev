import { expect, test } from '@playwright/test';

const PERSON_URL = 'http://127.0.0.1:8767/persons/yaroslav-halchenko/';
const PERSON_PID = 'xyzrins:persons/yaroslav-halchenko';

function isPersonRecordResponse(response) {
  const url = new URL(response.url());
  return (
    url.origin === 'http://127.0.0.1:8111'
    && url.pathname === '/con-protected/record'
    && url.searchParams.get('pid') === PERSON_PID
  );
}

test('the real Yaroslav edit link opens a populated anonymous Person form', async ({
  context,
  page,
}) => {
  const recordResponses = [];
  context.on('response', (response) => {
    if (isPersonRecordResponse(response)) {
      recordResponses.push(response);
    }
  });

  await page.goto(PERSON_URL);
  const editLink = page.getByRole('link', { name: 'Edit this record' });
  const href = await editLink.getAttribute('href');
  const editURL = new URL(href);
  expect(editURL.origin).toBe('http://127.0.0.1:3000');
  expect([...editURL.searchParams.keys()].sort()).toEqual([
    'edit',
    'pid',
    'sh:NodeShape',
  ]);
  expect(editURL.searchParams.get('sh:NodeShape')).toBe('dlthings:Thing');
  expect(editURL.searchParams.get('pid')).toBe(PERSON_PID);
  expect(editURL.searchParams.get('edit')).toBe('true');

  const popupPromise = context.waitForEvent('page');
  await editLink.click();
  const editor = await popupPromise;
  await editor.waitForLoadState('domcontentloaded');
  await expect.poll(() => recordResponses.length).toBeGreaterThan(0);
  expect(recordResponses.at(-1).status()).toBe(200);
  const requestHeaders = await recordResponses.at(-1).request().allHeaders();
  expect(requestHeaders).not.toHaveProperty('x-dumpthings-token');

  await expect(editor.getByText('Person', { exact: true }).first()).toBeVisible();
  await expect
    .poll(async () =>
      editor
        .locator('input')
        .evaluateAll((inputs) => inputs.map((item) => item.value)),
    )
    .toEqual(expect.arrayContaining(['Yaroslav', 'Halchenko']));
  await expect(editor.getByText('No items', { exact: true })).toHaveCount(0);
});

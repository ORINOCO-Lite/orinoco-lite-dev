import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const SERVICE_URL = 'http://127.0.0.1:8111';
export const COLLECTIONS = [
  'upstream-public',
  'upstream-protected',
  'con-public',
  'con-protected',
];
export const PROBE_PID = 'xyzrins:persons/_clean-migration-playwright-write-probe';
export const PROBE_CLASS = 'XYZPerson';

async function secret(root, name) {
  return (await readFile(path.join(root, 'build/local-stack', name), 'utf8')).trim();
}

async function request(url, { method = 'GET', token, body, allowMissing = false } = {}) {
  const headers = { Accept: 'application/json' };
  if (token !== undefined) {
    headers['X-DumpThings-Token'] = token;
  }
  let payload;
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const response = await fetch(url, { method, headers, body: payload });
  if (allowMissing && response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`${method} ${new URL(url).pathname} failed with ${response.status}`);
  }
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function recordURL(collection, boundary, pid) {
  const query = new URLSearchParams({ pid });
  return `${SERVICE_URL}/${collection}/${boundary}/record?${query}`;
}

export async function loadEditorToken(root) {
  return secret(root, 'editor-token');
}

export async function loadProbeRecord(root) {
  const source = await readFile(path.join(root, 'build/con-projection/records.jsonl'), 'utf8');
  const envelope = source
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line))
    .find((item) => item.record?.pid === 'xyzrins:persons/yaroslav-halchenko');
  if (envelope?.class_name !== PROBE_CLASS) {
    throw new Error('The canonical Yaroslav test fixture is unavailable');
  }
  const record = structuredClone(envelope.record);
  record.pid = PROBE_PID;
  record.display_label = 'Playwright Write Probe';
  record.formatted_name = 'Playwright Write Probe';
  record.given_name = 'Playwright';
  record.family_name = 'Probe';
  record.additional_names = ['Browser'];
  record.identifiers = [
    { notation: 'clean-migration-playwright-probe', schema_type: 'dlthings:Identifier' },
  ];
  return record;
}

export async function cleanupProbe(root) {
  const token = await secret(root, 'seed-token');
  for (const collection of COLLECTIONS) {
    for (const boundary of ['curated', 'incoming/local-editor']) {
      await request(recordURL(collection, boundary, PROBE_PID), {
        method: 'DELETE',
        token,
        allowMissing: true,
      });
    }
  }
}

export async function seedProbe(root, record) {
  const token = await secret(root, 'seed-token');
  await request(`${SERVICE_URL}/con-protected/curated/record/${PROBE_CLASS}`, {
    method: 'POST',
    token,
    body: record,
  });
}

export async function readProbeBoundaries(root) {
  const token = await secret(root, 'seed-token');
  const result = {};
  for (const collection of COLLECTIONS) {
    result[collection] = {};
    for (const boundary of ['curated', 'incoming/local-editor']) {
      result[collection][boundary] = await request(
        recordURL(collection, boundary, PROBE_PID),
        { token, allowMissing: true },
      );
    }
  }
  return result;
}

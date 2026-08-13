import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';

const CONTENT_TYPES = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml'],
  ['.ttl', 'text/turtle; charset=utf-8'],
  ['.webmanifest', 'application/manifest+json'],
]);

function normalizeMountPath(value) {
  const withLeading = value.startsWith('/') ? value : `/${value}`;
  return withLeading.endsWith('/') ? withLeading : `${withLeading}/`;
}

function resolveRequest(root, requestPath, mountPath) {
  if (!requestPath.startsWith(mountPath)) {
    return null;
  }
  let relative = decodeURIComponent(requestPath.slice(mountPath.length));
  if (!relative || relative.endsWith('/')) {
    relative += 'index.html';
  }
  const candidate = path.resolve(root, relative);
  const resolvedRoot = path.resolve(root);
  if (candidate !== resolvedRoot && !candidate.startsWith(`${resolvedRoot}${path.sep}`)) {
    return null;
  }
  return candidate;
}

export async function startStaticServer(profiles, initialProfile, options = {}) {
  let activeProfile = initialProfile;
  const mountPath = normalizeMountPath(options.mountPath ?? '/');
  const requests = [];
  const server = createServer(async (request, response) => {
    const url = new URL(request.url ?? '/', 'http://127.0.0.1');
    const root = profiles[activeProfile];
    const file = resolveRequest(root, url.pathname, mountPath);
    requests.push({
      method: request.method,
      profile: activeProfile,
      path: url.pathname,
      search: url.search,
    });
    if (file === null) {
      response.writeHead(404).end('Not found');
      return;
    }
    try {
      const info = await stat(file);
      if (!info.isFile()) {
        response.writeHead(404).end('Not found');
        return;
      }
      const extension = path.extname(file);
      response.setHeader(
        'Content-Type',
        CONTENT_TYPES.get(extension) ?? 'application/octet-stream',
      );
      if (path.basename(file) === 'graph.js' || path.basename(file) === 'graph.json') {
        response.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
      } else if (extension === '.html') {
        response.setHeader('Cache-Control', 'no-store');
      }
      response.setHeader('Content-Length', info.size);
      createReadStream(file).pipe(response);
    } catch (error) {
      if (error?.code === 'ENOENT') {
        response.writeHead(404).end('Not found');
        return;
      }
      response.writeHead(500).end('Static fixture failure');
    }
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (address === null || typeof address === 'string') {
    throw new Error('Could not determine static fixture address');
  }
  return {
    origin: `http://127.0.0.1:${address.port}`,
    mountPath,
    requests,
    use(profile) {
      if (!(profile in profiles)) {
        throw new Error(`Unknown static fixture profile: ${profile}`);
      }
      activeProfile = profile;
    },
    async close() {
      await new Promise((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
      });
    },
  };
}

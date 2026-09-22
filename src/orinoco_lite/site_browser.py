"""Optional Playwright inspection of explicitly selected rendered routes."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from threading import Thread

from .errors import DriverError

SCRIPT = r"""
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const fromWorkspace = createRequire(path.join(process.cwd(), 'package.json'));
let chromium;
try { ({chromium} = fromWorkspace('playwright')); }
catch { try { ({chromium} = fromWorkspace('@playwright/test')); }
catch { throw new Error('Playwright is unavailable in this workspace; install the maintainer browser dependencies.'); } }
(async () => {
  const options = JSON.parse(fs.readFileSync(0, 'utf8'));
  const browser = await chromium.launch({headless: true});
  const observations = [];
  try {
    const context = await browser.newContext({viewport: {width: 1280, height: 900}, reducedMotion: 'reduce'});
    await context.addInitScript(() => {
      let seed = 12345;
      Math.random = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
    });
    for (let index = 0; index < options.routes.length; index++) {
      const route = options.routes[index];
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(String(error.message)));
      page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
      page.on('requestfailed', request => errors.push(request.url().replace(options.origin, '') + ': ' + request.failure()?.errorText));
      let status = null;
      try {
        const response = await page.goto(options.origin + route, {waitUntil: 'networkidle', timeout: 30000});
        status = response?.status();
        await page.screenshot({path: path.join(options.output, `${index}.png`), fullPage: true, animations: 'disabled'});
      } catch (error) { errors.push(String(error.message)); }
      observations.push({route, status, errors});
      await page.close();
    }
  } finally { await browser.close(); }
  fs.writeFileSync(path.join(options.output, 'browser.json'), JSON.stringify(observations, null, 2) + '\n');
  fs.writeFileSync(path.join(options.output, 'browser-context.json'), JSON.stringify({schema_version: 1, browser: browser.version(), viewport: {width: 1280, height: 900}, reduced_motion: 'reduce', random_seed: 12345, screenshot_animations: 'disabled', routes: options.routes}, null, 2) + '\n');
  process.stdout.write(JSON.stringify(observations));
})().catch(error => {console.error(error.message); process.exit(2);});
"""


class _Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def inspect(root: Path, output: Path, routes: list[str], workspace: Path) -> list[dict]:
    if not routes or any(not route.startswith("/") or route.startswith("//") or ".." in route.split("/") for route in routes):
        raise DriverError("Browser routes must be explicit root-relative paths without traversal")
    if output.exists():
        raise DriverError(f"Browser evidence output already exists: {output}")
    output.mkdir(parents=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Handler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(["node", "-e", SCRIPT], cwd=workspace, capture_output=True,
                                text=True, input=json.dumps({
                                    "origin": f"http://127.0.0.1:{server.server_port}",
                                    "output": str(output), "routes": routes,
                                }))
        if result.returncode:
            raise DriverError(f"Browser inspection failed: {result.stderr.strip()}")
        return json.loads(result.stdout)
    except OSError as error:
        raise DriverError(f"Browser inspection could not start Node: {error}") from error
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

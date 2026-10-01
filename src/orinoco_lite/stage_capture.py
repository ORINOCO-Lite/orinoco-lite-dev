"""Capture selected live-site routes with GNU Wget, retaining HTTP evidence."""
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urljoin, urlsplit, unquote

from .errors import ConfigurationError, DriverError
from .progress import progress
from .stage_reports import write_operation


def register(commands):
    from .diagnostics import options
    capture = commands.add_parser('capture', help='capture live website routes and their same-host page assets with GNU Wget')
    capture.add_argument('url', help='HTTP(S) site base URL')
    options(capture, replace=False)
    capture.add_argument('--name', required=True, help='fresh capture directory name')
    capture.add_argument('--label', required=True, help='human label, e.g. Official site or Draft site')
    capture.add_argument('--branch-url', help='related upstream branch, not a verified deployed commit')
    capture.add_argument('--route', action='append', default=[], help='path relative to the base URL; repeatable (default: homepage)')
    capture.add_argument('--routes-from', type=Path, help='also request every HTML route in this retained site tree')
    capture.add_argument('--quota', default='100m', help='Wget download quota (default: 100m)')


@progress('Capturing live site with GNU Wget')
def capture(url, destination, *, label, branch_url=None, routes=(), routes_from=None, quota='100m'):
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError('Capture requires an HTTP(S) base URL without credentials, query, or fragment')
    if not parsed.path.endswith('/'):
        url += '/'
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ConfigurationError(f'Capture output already exists: {destination}')
    wget = shutil.which('wget')
    if not wget:
        raise DriverError('GNU Wget is required for live-site capture; install wget in the maintainer environment')
    paths = set(routes)
    if routes_from is not None:
        from .site_compare import files
        for name in files(routes_from):
            if name.endswith('.html'):
                paths.add(name[:-10] if name.endswith('index.html') else name)
    if not paths:
        paths.add('')
    urls = []
    for path in sorted(paths):
        path = path.lstrip('/')
        resolved = urljoin(url, path)
        if (urlsplit(path).scheme or urlsplit(path).netloc or '..' in unquote(path).split('/')
                or any(c in path for c in '\r\n') or not resolved.startswith(url)):
            raise ConfigurationError(f'Capture route must remain under the site base URL: {path!r}')
        urls.append(resolved)
    destination.mkdir(parents=True)
    tree = destination / 'site'
    tree.mkdir()
    seeds = destination / 'routes.txt'
    seeds.write_text('\n'.join(urls) + '\n', encoding='utf-8')
    started = datetime.now(timezone.utc).isoformat()
    command = [wget, '--no-config', '--no-netrc', '--no-cookies', '--page-requisites',
               '--no-host-directories', '--no-parent', '--domains=' + parsed.hostname,
               '--cut-dirs=' + str(len([p for p in parsed.path.split('/') if p])),
               '--timeout=20', '--tries=1', '--wait=0.05', '--quota=' + quota,
               '--directory-prefix=' + str(tree), '--input-file=' + str(seeds),
               '--output-file=' + str(destination / 'wget.log'),
               '--warc-file=' + str(destination / 'http'), '--warc-cdx']
    result = subprocess.run(command, capture_output=True, text=True)
    finished = datetime.now(timezone.utc).isoformat()
    version = subprocess.run([wget, '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    target = {'label': label, 'url': url, 'captured_at': started, 'capture_finished_at': finished}
    if branch_url:
        target['branch_url'] = branch_url
    from collections import Counter
    responses = {}
    index = destination / 'http.cdx'
    if index.exists():
        for line in index.read_text().splitlines()[1:]:
            fields = line.split()
            if len(fields) > 4 and fields[4].isdigit():
                responses[fields[0]] = int(fields[4])
    statuses = Counter(responses.values())
    complete = (result.returncode in {0, 8} and all(u in responses for u in urls)
                and all(200 <= code < 400 or code in {404, 410} for code in responses.values()))
    target['capture_scope'] = f'{len(urls)} requested routes plus same-host page assets'
    target['http_responses'] = ', '.join(f'{code}: {count}' for code, count in sorted(statuses.items())) or 'No indexed responses'
    target['capture_status'] = 'HTTP responses retained' if complete else 'Incomplete retrieval'

    write_operation(tree, operation='site-capture', inputs={'requested-routes': seeds}, command=command,
                    context={'target': target, 'capture': {
                        'requested_routes': len(urls), 'routes': [u[len(url):] for u in urls],
                        'retrieval_complete': complete, 'exit_code': result.returncode,
                        'tool': version, 'coverage': 'Selected routes and Wget-discovered same-host page requisites; no JavaScript execution or arbitrary link crawl.',
                        'http_evidence': 'http.warc.gz', 'http_index': 'http.cdx', 'log': 'wget.log'},
                        'status': 'complete' if complete else 'failed'})
    return {'path': str(tree), 'target': target, 'retrieval_complete': complete, 'exit_code': result.returncode,
            'http_evidence': str(destination / 'http.warc.gz'), 'log': str(destination / 'wget.log')}


def execute(args, root):
    from .diagnostics import explicit_path
    if Path(args.name).name != args.name or args.name in {'.', '..'}:
        raise ConfigurationError('Capture name must be a single directory name')
    result = capture(args.url, root / 'captures' / args.name, label=args.label,
                     branch_url=args.branch_url, routes=args.route,
                     routes_from=explicit_path(args, args.routes_from) if args.routes_from else None, quota=args.quota)
    from .stage_reports import canonical
    print(canonical(result))
    return 0 if result['retrieval_complete'] else 1

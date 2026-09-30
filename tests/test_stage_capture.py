"""Capture real HTTP responses through Wget; retain partial evidence honestly."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from threading import Thread
import shutil

import pytest
from orinoco_lite.stage_capture import capture
from orinoco_lite.stage_reports import operation_receipt
from orinoco_lite.errors import ConfigurationError


def test_capture_retains_html_bytes_assets_and_404_evidence(tmp_path):
    if not shutil.which('wget'):
        pytest.skip('GNU Wget unavailable')
    source = tmp_path / 'served'
    source.mkdir()
    content = b'<html><img src="/asset.png"><a href="/not-requested/">link</a></html>'
    (source / 'index.html').write_bytes(content)
    (source / 'asset.png').write_bytes(b'image fixture')
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(source)))
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        result = capture(f'http://127.0.0.1:{server.server_port}/', tmp_path / 'capture',
                         label='Official site', routes=['', 'missing/'], branch_url='https://example.org/branch/published')
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert result['retrieval_complete']
    tree = tmp_path / 'capture/site'
    assert (tree / 'index.html').read_bytes() == content
    assert (tree / 'asset.png').read_bytes() == b'image fixture'
    assert not (tree / 'not-requested').exists()
    receipt = operation_receipt(tree)
    assert receipt['context']['target']['label'] == 'Official site'
    assert '404:' in receipt['context']['target']['http_responses']
    assert (tree.parent / 'http.warc.gz').is_file()
    assert '/missing/' in (tree.parent / 'http.cdx').read_text()


@pytest.mark.parametrize('url', ['file:///tmp/', 'https://user:password@example.org/', 'https://example.org/?secret=value'])
def test_capture_rejects_nonpublic_url_forms_before_writing(tmp_path, url):
    with pytest.raises(ConfigurationError):
        capture(url, tmp_path / 'capture', label='test')
    assert not (tmp_path / 'capture').exists()

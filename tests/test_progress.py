import io
import json
import sys
from threading import Event

import pytest

from orinoco_lite.progress import progress


class ObservedStream(io.StringIO):
    def __init__(self):
        super().__init__()
        self.flushed = Event()

    def flush(self):
        self.flushed.set()
        super().flush()


def test_slow_operation_reports_before_completion_without_polluting_json(monkeypatch, capsys):
    stream = ObservedStream()
    monkeypatch.setattr(sys, "stderr", stream)
    with progress("Reading records"):
        assert stream.flushed.wait(3), "No progress while the operation was still running"
        assert stream.getvalue() == "Reading records...\n"
    print(json.dumps({"records": 42}))
    assert json.loads(capsys.readouterr().out) == {"records": 42}


@pytest.mark.parametrize("fail", [False, True])
def test_finished_operations_leave_no_delayed_message(monkeypatch, fail):
    stream = ObservedStream()
    monkeypatch.setattr(sys, "stderr", stream)
    try:
        with progress("Reading records"):
            if fail:
                raise ValueError("invalid record")
    except ValueError as error:
        assert str(error) == "invalid record"
    assert not stream.flushed.wait(1.1)
    assert stream.getvalue() == ""


@pytest.mark.parametrize("fail", [False, True])
def test_site_verification_reports_while_waiting_for_http(monkeypatch, capsys, tmp_path, fail):
    from urllib.error import URLError
    from orinoco_lite import local_preview

    (tmp_path / "index.html").write_text('<link rel="stylesheet" href="/site.css">')
    (tmp_path / "site.css").write_text("body {}")
    stream = ObservedStream()
    monkeypatch.setattr(sys, "stderr", stream)
    urlopen = local_preview.urlopen

    def delayed_open(*args, **kwargs):
        assert stream.flushed.wait(3), "No feedback while waiting for an HTTP response"
        if fail:
            raise URLError("unavailable")
        return urlopen(*args, **kwargs)

    monkeypatch.setattr(local_preview, "urlopen", delayed_open)
    status = local_preview.main([str(tmp_path)])
    output = capsys.readouterr().out
    assert "Checking local HTTP references...\n" in stream.getvalue()
    if fail:
        assert status == 1
        assert output == ""
        assert "unavailable" in stream.getvalue()
    else:
        assert status == 0
        assert json.loads(output)["files"] == 2


def test_serve_flushes_ready_message_before_waiting(monkeypatch, capsys, tmp_path):
    from types import SimpleNamespace
    from orinoco_lite import cli

    (tmp_path / "index.html").write_text("preview")
    stream = ObservedStream()
    monkeypatch.setattr(sys, "stderr", stream)
    monkeypatch.setattr(cli, "_workspace", lambda args: SimpleNamespace(site_name="Example"))

    class Server:
        server_address = ("127.0.0.1", 12345)

        def serve_forever(self):
            assert stream.flushed.is_set()
            assert "http://127.0.0.1:12345/" in stream.getvalue()
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr(cli, "ThreadingHTTPServer", lambda *args: Server())
    args = cli._parser().parse_args(["serve", "--directory", str(tmp_path)])
    assert cli._serve(args) == 0
    assert capsys.readouterr().out == ""

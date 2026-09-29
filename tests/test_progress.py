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

"""Report slow operations without adding noise to quick commands or stdout."""

from contextlib import contextmanager
import sys
from threading import Timer


@contextmanager
def progress(message: str):
    """Emit one flushed stderr note if the operation lasts longer than a second."""
    timer = Timer(1.0, lambda: print(f"{message}...", file=sys.stderr, flush=True))
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        timer.join()

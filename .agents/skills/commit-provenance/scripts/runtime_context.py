"""Read fresh, thread-scoped turn metadata when no rollout transcript exists."""

import json
from pathlib import Path
import re
import sqlite3
import sys
import time


def resolve(database, thread_id, now=None):
    now = time.time() if now is None else now
    pattern = re.compile(
        r'turn\{[^{}]*thread\.id=' + re.escape(thread_id)
        + r' turn\.id=([^\s}]+) model=([^\s}]+) '
        r'codex\.turn\.reasoning_effort=([^\s}]+)'
    )
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            'SELECT ts, feedback_log_body FROM logs WHERE thread_id = ? '
            'ORDER BY id DESC LIMIT 200', (thread_id,)
        )
        for timestamp, body in rows:
            match = pattern.search(body or '')
            if not match:
                continue
            if not 0 <= now - timestamp <= 300:
                raise ValueError('runtime turn evidence is not fresh (five-minute limit)')
            turn, model, effort = match.groups()
            if effort not in {'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'}:
                raise ValueError('unrecognized runtime reasoning effort')
            return {'turn_id': turn, 'model': model, 'reasoning_effort': effort}
    raise ValueError('no matching runtime turn metadata for this thread')


if __name__ == '__main__':
    try:
        print(json.dumps(resolve(sys.argv[1], sys.argv[2])))
    except (sqlite3.Error, ValueError, OSError) as error:
        sys.exit(f'commit-provenance: {error}')

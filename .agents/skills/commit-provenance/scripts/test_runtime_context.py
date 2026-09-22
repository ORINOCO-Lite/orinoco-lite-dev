import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime_context import resolve


class RuntimeContextTests(unittest.TestCase):
    def test_newest_turn_and_thread_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'logs.sqlite'
            with sqlite3.connect(database) as connection:
                connection.execute('CREATE TABLE logs (id INTEGER PRIMARY KEY, ts INTEGER, thread_id TEXT, feedback_log_body TEXT)')
                for thread, turn, effort in [('side', 'old', 'low'), ('side', 'new', 'medium'), ('parent', 'other', 'high')]:
                    body = f'turn{{thread.id={thread} turn.id={turn} model=gpt-6-astra codex.turn.reasoning_effort={effort}}}'
                    connection.execute('INSERT INTO logs (ts,thread_id,feedback_log_body) VALUES (?,?,?)', (1000, thread, body))
            self.assertEqual(resolve(database, 'side', now=1001), {
                'turn_id': 'new', 'model': 'gpt-6-astra', 'reasoning_effort': 'medium'})
            with self.assertRaisesRegex(ValueError, 'not fresh'):
                resolve(database, 'side', now=1400)
            with self.assertRaisesRegex(ValueError, 'no matching'):
                resolve(database, 'missing', now=1001)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'missing.sqlite'
            with self.assertRaises(sqlite3.Error):
                resolve(database, 'side')
            self.assertFalse(database.exists())


if __name__ == '__main__':
    unittest.main()

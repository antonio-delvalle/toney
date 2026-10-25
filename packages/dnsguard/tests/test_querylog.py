import os
import tempfile
import time
import unittest

from dnsguard.querylog import QueryLog


class QueryLogTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = self.folder.name

    def _record(self, name="ads.example.net", client="192.0.2.10"):
        return {
            "ts": "2026-01-02T03:04:05Z",
            "client": client,
            "name": name,
            "type": "A",
            "decision": "block",
            "rule": "||ads.example.net^",
        }

    def test_writes_one_file_per_day(self):
        log = QueryLog(self.directory, retention_days=5)
        path = log.write(self._record())
        self.assertTrue(path.endswith(".jsonl"))
        self.assertTrue(os.path.isfile(path))
        log.close()

    def test_tail_returns_newest_first(self):
        log = QueryLog(self.directory, retention_days=5)
        log.write(self._record(name="first.example.net"))
        log.write(self._record(name="second.example.net"))
        lines = log.tail(limit=10)
        self.assertEqual(lines[0]["name"], "second.example.net")
        log.close()

    def test_tail_filters_by_name_and_client(self):
        log = QueryLog(self.directory, retention_days=5)
        log.write(self._record(name="ads.example.net"))
        log.write(self._record(name="cdn.example.net", client="192.0.2.99"))
        self.assertEqual(len(log.tail(limit=10, needle="ads")), 1)
        self.assertEqual(len(log.tail(limit=10, client="192.0.2.99")), 1)
        log.close()

    def test_size_cap_rolls_the_file_over(self):
        log = QueryLog(self.directory, retention_days=5, max_bytes=1024)
        for _ in range(60):
            log.write(self._record())
        files = [f for f in os.listdir(self.directory)]
        self.assertTrue(any(f.endswith(".jsonl.1.gz") for f in files))
        log.close()

    def test_sweep_removes_files_outside_the_window(self):
        old = os.path.join(self.directory, "2000-01-01.jsonl")
        with open(old, "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        log = QueryLog(self.directory, retention_days=5)
        removed = log.sweep()
        self.assertIn(old, removed)
        self.assertFalse(os.path.exists(old))
        log.close()

    def test_sweep_keeps_recent_files(self):
        log = QueryLog(self.directory, retention_days=5)
        log.write(self._record())
        removed = log.sweep()
        self.assertEqual(removed, [])
        log.close()

    def test_files_and_total_bytes(self):
        log = QueryLog(self.directory, retention_days=5)
        log.write(self._record())
        self.assertEqual(len(log.files()), 1)
        self.assertGreater(log.total_bytes(), 0)
        log.close()

    def test_clients_lists_the_addresses_in_the_log(self):
        log = QueryLog(self.directory, retention_days=5)
        log.write(self._record(client="192.0.2.10"))
        log.write(self._record(client="192.0.2.11"))
        log.write(self._record(client="192.0.2.10"))
        self.assertEqual(log.clients(), ["192.0.2.10", "192.0.2.11"])
        log.close()

    def test_clients_puts_the_most_recent_address_first(self):
        log = QueryLog(self.directory, retention_days=5)
        log.write(self._record(client="192.0.2.10"))
        log.write(self._record(client="192.0.2.11"))
        self.assertEqual(log.clients(), ["192.0.2.11", "192.0.2.10"])
        log.close()

    def test_clients_stops_at_the_limit(self):
        log = QueryLog(self.directory, retention_days=5)
        log.write(self._record(client="192.0.2.10"))
        log.write(self._record(client="192.0.2.11"))
        log.write(self._record(client="192.0.2.12"))
        self.assertEqual(len(log.clients(limit=2)), 2)
        log.close()

    def test_clients_of_an_empty_log(self):
        log = QueryLog(self.directory, retention_days=5)
        self.assertEqual(log.clients(), [])
        log.close()


if __name__ == "__main__":
    unittest.main()

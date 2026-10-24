import os
import tempfile
import unittest

from dnsguard import rules, wire
from dnsguard.config import Config
from dnsguard.service import Service


class FakeResolver:
    def __init__(self, payload=None):
        self.payload = payload
        self.queries = []

    def query(self, qname, qtype, wire_query=None, transaction_id=None):
        self.queries.append((qname, qtype))
        if self.payload is None:
            raise RuntimeError("no upstream")
        return self.payload, False

    def configure(self, **kwargs):
        pass


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.rule_file = os.path.join(self.folder.name, "rules.txt")
        with open(self.rule_file, "w", encoding="utf-8") as handle:
            handle.write("||ads.example.net^\n@@||cdn.example.net^\n")
        config = Config({
            "listen": "127.0.0.1:0",
            "upstream": ["192.0.2.53"],
            "log_dir": os.path.join(self.folder.name, "logs"),
            "rules": [self.rule_file],
        })
        self.service = Service(config)
        self.addCleanup(self.service.stop)
        self.service.load_rules()

    def _query(self, name, qtype=1):
        return wire.build_query(0x4242, name, qtype)

    def test_blocked_name_returns_nxdomain(self):
        response = self.service.handle_query(self._query("pixel.ads.example.net"),
                                             "192.0.2.10")
        self.assertEqual(wire.rcode(response), 3)
        self.assertEqual(self.service.counters["block"], 1)
        self.assertEqual(self.service.counters["total"], 1)

    def test_allowed_name_is_forwarded(self):
        canned = wire.build_response(0x4242, 0x0100, wire.encode_name("cdn.example.net") + b"\x00\x01\x00\x01")
        self.service.resolver = FakeResolver(canned)
        response = self.service.handle_query(self._query("cdn.example.net"), "192.0.2.10")
        self.assertIsNotNone(response)
        self.assertEqual(self.service.counters["allow"], 1)

    def test_allow_rule_wins_over_block(self):
        self.service.rules = rules.RuleSet([
            rules.parse_rule("||example.net^"),
            rules.parse_rule("@@||cdn.example.net^"),
        ])
        canned = wire.build_response(1, 0x0100, b"\x00")
        self.service.resolver = FakeResolver(canned)
        self.service.handle_query(self._query("cdn.example.net"), "192.0.2.10")
        self.assertEqual(self.service.counters["block"], 0)

    def test_malformed_query_is_counted_as_error(self):
        self.assertIsNone(self.service.handle_query(b"\x00", "192.0.2.10"))
        self.assertEqual(self.service.counters["errors"], 1)

    def test_client_counters(self):
        self.service.handle_query(self._query("ads.example.net"), "192.0.2.10")
        clients = self.service.status()["clients"]
        self.assertEqual(clients["192.0.2.10"]["blocked"], 1)
        self.assertEqual(clients["192.0.2.10"]["total"], 1)

    def test_status_shape(self):
        status = self.service.status()
        self.assertEqual(status["name"], "dnsguard")
        self.assertIn("counters", status)
        self.assertEqual(status["rules"]["count"], 2)
        self.assertEqual(status["log"]["retention_days"], 5)

    def test_stats_shape(self):
        self.service.handle_query(self._query("ads.example.net"), "192.0.2.10")
        stats = self.service.stats(300)
        self.assertIn("buckets", stats)
        self.assertEqual(stats["top_blocked"][0]["name"], "ads.example.net.")


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.rule_file = os.path.join(self.folder.name, "rules.txt")
        with open(self.rule_file, "w", encoding="utf-8") as handle:
            handle.write("||ads.example.net^\n")
        config = Config({
            "listen": "127.0.0.1:0",
            "upstream": ["192.0.2.53"],
            "log_dir": os.path.join(self.folder.name, "logs"),
            "rules": [self.rule_file],
        })
        self.service = Service(config)
        self.addCleanup(self.service.stop)
        self.service.load_rules()

    def test_rules_list(self):
        data = self.service.dispatch("rules.list", {})
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["rules"][0]["action"], "block")

    def test_rules_reload(self):
        data = self.service.dispatch("rules.reload", {})
        self.assertEqual(data["count"], 1)

    def test_rules_set_replaces_the_rule_set(self):
        new_file = os.path.join(self.folder.name, "new.txt")
        with open(new_file, "w", encoding="utf-8") as handle:
            handle.write("||one.example^\n||two.example^\n")
        data = self.service.dispatch("rules.set", {"path": new_file})
        self.assertEqual(data["count"], 2)

    def test_logs_tail(self):
        self.service.handle_query(wire.build_query(1, "ads.example.net", 1), "192.0.2.10")
        data = self.service.dispatch("logs.tail", {"limit": 5})
        self.assertEqual(len(data["lines"]), 1)
        self.assertEqual(data["lines"][0]["decision"], "block")

    def test_config_get_and_set(self):
        data = self.service.dispatch("config.get", {})
        self.assertEqual(data["listen"], "127.0.0.1:0")
        updated = self.service.dispatch("config.set", {"upstream": ["192.0.2.54"]})
        self.assertIn("upstream", updated["changed"])

    def test_control_path_cannot_be_changed(self):
        with self.assertRaises(ValueError):
            self.service.dispatch("config.set", {"control": "/tmp/other.sock"})

    def test_unknown_command(self):
        with self.assertRaises(ValueError):
            self.service.dispatch("frobnicate", {})

    def test_invalid_params(self):
        with self.assertRaises(ValueError):
            self.service.dispatch("stats", "not-an-object")


if __name__ == "__main__":
    unittest.main()

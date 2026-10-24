"""Tests for the rules editor and the router view."""

import os
import tempfile
import unittest

import support
from toney.ui import ToneyApp
from toney.views.router import RouterView
from toney.views.rules import RulesView


class FakeClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.requests = []
        self.closed = False

    def request(self, cmd, params=None):
        self.requests.append((cmd, params))
        value = self.responses.get(cmd)
        if isinstance(value, Exception):
            raise value
        return value if value is not None else {}

    def close(self):
        self.closed = True


class RulesEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rules_file = os.path.join(self.tmp.name, "rules.blocklist")
        self.config = {
            "control_socket": os.path.join(self.tmp.name, "dnsguard.sock"),
            "rules_file": self.rules_file,
            "service": {"command": ["python3", "-m", "dnsguard", "serve"], "cwd": None, "env": {}},
            "config_path": "/etc/toney/dnsguard.json",
        }
        self.client = FakeClient({
            "rules.list": {
                "count": 2,
                "rules": [
                    {"pattern": "||ads.example.net^", "action": "block", "source": "a", "line": 1},
                    {"pattern": "||cdn.example.net^", "action": "allow", "source": "a", "line": 2},
                ],
            },
            "rules.set": {"count": 3, "loaded_at": "2026-01-02T03:04:05Z"},
        })
        self.app = ToneyApp(self.config, client_factory=lambda: self.client)
        self.addCleanup(self.app.cleanup)
        self.view = self.app.views[2]
        self.assertIsInstance(self.view, RulesView)
        self.view.refresh()

    def test_add_block_rule(self):
        self.app.prompt = lambda label, initial="": "tracker.example.net"
        self.view.add_rule("block")
        with open(self.rules_file, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("||tracker.example.net^", content)
        self.assertIn("||ads.example.net^", content)
        self.assertIn("@@||cdn.example.net^", content)

    def test_add_keep_rule(self):
        self.app.prompt = lambda label, initial="": "static.example.net"
        self.view.add_rule("allow")
        with open(self.rules_file, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("@@||static.example.net^", content)

    def test_invalid_domain_is_rejected(self):
        self.app.prompt = lambda label, initial="": "not a domain"
        self.assertFalse(self.view.add_rule("block"))
        self.assertFalse(os.path.exists(self.rules_file))

    def test_rules_set_is_sent_to_the_service(self):
        self.app.prompt = lambda label, initial="": "tracker.example.net"
        self.view.add_rule("block")
        commands = [cmd for cmd, _ in self.client.requests]
        self.assertIn("rules.set", commands)

    def test_delete_removes_the_selected_rule(self):
        self.view.selected = 0
        self.view.delete_selected()
        with open(self.rules_file, encoding="utf-8") as handle:
            content = handle.read()
        self.assertNotIn("||ads.example.net^", content)
        self.assertIn("||cdn.example.net^", content)

    def test_delete_without_rules_fails(self):
        self.view.rules = []
        self.assertFalse(self.view.delete_selected())

    def test_rule_text_keeps_the_allow_marker(self):
        text = self.view.rule_text(self.view.rules)
        self.assertIn("@@||cdn.example.net^", text)


class RouterViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = {
            "control_socket": os.path.join(self.tmp.name, "dnsguard.sock"),
            "service": {"command": ["python3", "-m", "dnsguard", "serve"], "cwd": None, "env": {}},
            "config_path": "/etc/toney/dnsguard.json",
        }
        self.client = FakeClient({
            "router.status": {
                "configured": True,
                "installed": True,
                "matches": True,
                "remote_path": "/etc/dnsmasq.d/toney.conf",
                "host": "192.0.2.1",
                "bytes": 128,
            },
            "router.deploy": {"deployed": True, "rules": 67, "skipped": 2, "bytes": 128},
            "router.rollback": {"rolled_back": True, "restored": "backup.conf", "removed": False},
        })
        self.app = ToneyApp(self.config, client_factory=lambda: self.client)
        self.addCleanup(self.app.cleanup)
        self.view = self.app.views[4]
        self.assertIsInstance(self.view, RouterView)

    def test_refresh_reads_the_status(self):
        self.view.refresh()
        self.assertTrue(self.view.state["configured"])

    def test_deploy_calls_the_service(self):
        self.view.deploy()
        commands = [cmd for cmd, _ in self.client.requests]
        self.assertIn("router.deploy", commands)

    def test_rollback_calls_the_service(self):
        self.view.rollback()
        commands = [cmd for cmd, _ in self.client.requests]
        self.assertIn("router.rollback", commands)

    def test_keys_are_handled(self):
        self.assertTrue(self.view.handle_key(ord("d")))
        self.assertTrue(self.view.handle_key(ord("b")))
        self.assertFalse(self.view.handle_key(ord("z")))


if __name__ == "__main__":
    unittest.main()

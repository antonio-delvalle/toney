"""Tests for the application shell that do not need a terminal."""

import os
import tempfile
import unittest

import support
from toney.client import ServiceUnreachable
from toney.ui import ToneyApp


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


class AppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = {
            "control_socket": os.path.join(self.tmp.name, "dnsguard.sock"),
            "service": {"command": ["python3", "-m", "dnsguard", "serve"], "cwd": None, "env": {}},
            "config_path": "/etc/toney/dnsguard.json",
        }

    def build(self, responses=None):
        client = FakeClient(responses)
        app = ToneyApp(self.config, client_factory=lambda: client)
        self.addCleanup(app.cleanup)
        return app, client

    def test_views_are_available(self):
        app, _client = self.build()
        self.assertEqual(
            [view.name for view in app.views],
            ["dashboard", "logs", "rules", "service", "router"],
        )

    def test_number_keys_switch_the_view(self):
        app, _client = self.build()
        app.handle_key(ord("3"))
        self.assertEqual(app.current, 2)
        app.handle_key(ord("1"))
        self.assertEqual(app.current, 0)

    def test_tab_switches_to_the_next_view(self):
        app, _client = self.build()
        app.handle_key(ord("\t"))
        self.assertEqual(app.current, 1)

    def test_quit_stops_the_loop(self):
        app, _client = self.build()
        self.assertTrue(app.running)
        app.handle_key(ord("q"))
        self.assertFalse(app.running)

    def test_a_socket_error_does_not_break_the_application(self):
        app, client = self.build({"status": ServiceUnreachable("no socket")})
        app.refresh_view()
        self.assertEqual(app.status_kind, "error")
        self.assertIn("no socket", app.status_message)
        self.assertTrue(app.running)

    def test_service_state_follows_the_socket(self):
        app, _client = self.build({"status": {"name": "dnsguard"}})
        self.assertEqual(app.service_state(), "stopped")
        app.refresh_view()
        self.assertEqual(app.service_state(), "running")

    def test_help_overlay_opens_and_closes(self):
        app, _client = self.build()
        app.handle_key(ord("?"))
        self.assertIsNotNone(app.overlay)
        app.handle_key(ord("q"))
        self.assertIsNone(app.overlay)

    def test_config_editor_is_opened_from_the_service_configuration(self):
        app, client = self.build({"config.get": {"listen": "0.0.0.0:5353"}})
        app.handle_key(ord("c"))
        self.assertIsNotNone(app.overlay)
        self.assertIn(("config.get", {}), client.requests)


if __name__ == "__main__":
    unittest.main()

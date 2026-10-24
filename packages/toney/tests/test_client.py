"""Tests for the control protocol client."""

import os
import tempfile
import unittest

import support
from toney.client import (
    CommandError,
    CommandNotSupported,
    ControlClient,
    ProtocolError,
    ServiceUnreachable,
)


class ControlClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "control.sock")

    def start_server(self, commands=None, raw=None):
        server = support.FakeServer(self.path, commands, raw).start()
        self.addCleanup(server.stop)
        return server

    def test_status_round_trip(self):
        self.start_server(
            {"status": {"name": "dnsguard", "version": "0.1.0", "pid": 4242}}
        )
        with ControlClient(self.path) as client:
            data = client.status()
        self.assertEqual(data["name"], "dnsguard")
        self.assertEqual(data["version"], "0.1.0")
        self.assertEqual(data["pid"], 4242)

    def test_request_carries_id_cmd_and_params(self):
        server = self.start_server({"logs.tail": {"lines": []}})
        with ControlClient(self.path) as client:
            client.logs_tail(limit=10, text_filter="ads", client="192.0.2.10")
        request = server.requests[-1]
        self.assertIn("id", request)
        self.assertEqual(request["cmd"], "logs.tail")
        self.assertEqual(request["params"]["limit"], 10)
        self.assertEqual(request["params"]["filter"], "ads")
        self.assertEqual(request["params"]["client"], "192.0.2.10")

    def test_unknown_command_is_reported_as_not_supported(self):
        self.start_server({})
        with ControlClient(self.path) as client:
            with self.assertRaises(CommandNotSupported) as ctx:
                client.request("frobnicate")
        self.assertIn("unknown command", str(ctx.exception))

    def test_command_failure_raises_command_error(self):
        self.start_server({"status": support.Error("invalid params: window_s")})
        with ControlClient(self.path) as client:
            with self.assertRaises(CommandError) as ctx:
                client.status()
        self.assertIn("invalid params", str(ctx.exception))
        self.assertNotIsInstance(ctx.exception, CommandNotSupported)

    def test_missing_socket_raises_service_unreachable(self):
        with ControlClient(self.path, retries=0) as client:
            with self.assertRaises(ServiceUnreachable):
                client.status()

    def test_refused_connection_raises_service_unreachable(self):
        support.refused_socket(self.path)
        with ControlClient(self.path, retries=0) as client:
            with self.assertRaises(ServiceUnreachable):
                client.status()

    def test_malformed_reply_raises_protocol_error(self):
        self.start_server(raw=b"this is not json\n")
        with ControlClient(self.path, retries=0) as client:
            with self.assertRaises(ProtocolError):
                client.status()

    def test_reply_id_mismatch_raises_protocol_error(self):
        self.start_server(raw=b'{"id": 999, "ok": true, "data": {}}\n')
        with ControlClient(self.path, retries=0) as client:
            with self.assertRaises(ProtocolError):
                client.status()

    def test_closed_connection_raises_protocol_error(self):
        self.start_server(raw=b"")
        with ControlClient(self.path, timeout=0.5, retries=0) as client:
            with self.assertRaises(ProtocolError):
                client.status()

    def test_shutdown_command_is_sent(self):
        server = self.start_server({"shutdown": {"stopping": True}})
        with ControlClient(self.path) as client:
            client.shutdown()
        self.assertEqual(server.requests[-1]["cmd"], "shutdown")

    def test_typed_helpers_use_the_documented_commands(self):
        server = self.start_server(
            {
                "status": {},
                "stats": {"window_s": 300},
                "rules.list": {"count": 0, "rules": []},
                "rules.reload": {"count": 0, "rules": []},
                "rules.set": {"count": 0, "rules": []},
                "logs.tail": {"lines": []},
                "config.get": {"listen": "0.0.0.0:5353"},
                "config.set": {"listen": "0.0.0.0:5353"},
                "upstream.set": {"upstream": ["198.51.100.53"]},
                "shutdown": {},
            }
        )
        with ControlClient(self.path) as client:
            client.status()
            client.stats(window_s=60)
            client.rules_list()
            client.rules_reload()
            client.rules_set("/tmp/toney-rules.blocklist")
            client.logs_tail(limit=5)
            client.config_get()
            client.config_set({"listen": "0.0.0.0:5353"})
            client.upstream_set(servers=["198.51.100.53"])
            client.shutdown()
        commands = [request["cmd"] for request in server.requests]
        self.assertEqual(
            commands,
            [
                "status",
                "stats",
                "rules.list",
                "rules.reload",
                "rules.set",
                "logs.tail",
                "config.get",
                "config.set",
                "upstream.set",
                "shutdown",
            ],
        )
        rules_set = server.requests[4]
        self.assertEqual(
            rules_set["params"]["path"], "/tmp/toney-rules.blocklist"
        )
        upstream = server.requests[8]
        self.assertEqual(upstream["params"]["servers"], ["198.51.100.53"])


if __name__ == "__main__":
    unittest.main()

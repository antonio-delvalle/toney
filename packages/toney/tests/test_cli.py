"""Tests for the command line interface."""

import contextlib
import io
import os
import tempfile
import unittest

import support
from toney.cli import build_parser, main


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "control.sock")

    def run_cli(self, argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_check_reports_an_unreachable_service(self):
        code, output = self.run_cli(["--check", "--control", self.path])
        self.assertEqual(code, 1)
        self.assertIn("service not reachable", output)
        self.assertEqual(len(output.strip().splitlines()), 1)

    def test_check_reports_a_reachable_service(self):
        server = support.FakeServer(
            self.path, {"status": {"name": "dnsguard", "version": "0.1.0", "pid": 99}}
        ).start()
        self.addCleanup(server.stop)
        code, output = self.run_cli(["--check", "--control", self.path])
        self.assertEqual(code, 0)
        self.assertIn("service reachable", output)
        self.assertIn("dnsguard", output)

    def test_check_does_not_create_the_socket(self):
        code, _output = self.run_cli(["--check", "--control", self.path])
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(self.path))

    def test_help_exits_successfully(self):
        with self.assertRaises(SystemExit) as ctx:
            with contextlib.redirect_stdout(io.StringIO()):
                build_parser().parse_args(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_unknown_option_is_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            with contextlib.redirect_stdout(io.StringIO()):
                build_parser().parse_args(["--nonsense"])
        self.assertNotEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()

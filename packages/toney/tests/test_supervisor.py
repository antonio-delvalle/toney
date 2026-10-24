"""Tests for the service supervisor."""

import os
import sys
import tempfile
import time
import unittest
from unittest import mock

import support
from toney.client import ToneyError
from toney.supervisor import ServiceSupervisor

DUMMY_COMMAND = [sys.executable, "-c", "import time; time.sleep(30)"]


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.socket_path = os.path.join(self.tmp.name, "dnsguard.sock")
        self.config = {
            "control_socket": self.socket_path,
            "service": {"command": list(DUMMY_COMMAND), "cwd": None, "env": {}},
            "config_path": "/etc/toney/dnsguard.json",
        }

    def build(self, client_factory=None):
        supervisor = ServiceSupervisor(
            self.config, client_factory=client_factory, state_dir=self.tmp.name
        )
        self.addCleanup(supervisor.cleanup)
        return supervisor

    def test_running_is_false_without_a_socket(self):
        supervisor = self.build()
        self.assertFalse(supervisor.running())

    def test_running_is_true_when_the_service_answers(self):
        client = mock.MagicMock()
        client.status.return_value = {"name": "dnsguard"}
        supervisor = self.build(client_factory=lambda: client)
        self.assertTrue(supervisor.running())

    def test_start_does_not_spawn_a_second_service(self):
        client = mock.MagicMock()
        client.status.return_value = {"name": "dnsguard"}
        supervisor = self.build(client_factory=lambda: client)
        supervisor.start()
        self.assertIsNone(supervisor._child)

    def test_start_records_a_live_pid(self):
        supervisor = self.build()
        pid = supervisor.start()
        self.assertIsInstance(pid, int)
        self.assertGreater(pid, 0)
        self.assertTrue(supervisor._pid_alive(pid))
        self.assertEqual(supervisor.pid, pid)

    def test_stop_terminates_the_process(self):
        supervisor = self.build()
        pid = supervisor.start()
        self.assertTrue(supervisor.stop(timeout=2))
        self.assertFalse(supervisor._pid_alive(pid))

    def test_stop_is_safe_to_call_twice(self):
        supervisor = self.build()
        supervisor.start()
        self.assertTrue(supervisor.stop(timeout=2))
        self.assertTrue(supervisor.stop(timeout=1))

    def test_stop_asks_the_service_to_shutdown(self):
        client = mock.MagicMock()
        client.shutdown.return_value = {}
        supervisor = self.build(client_factory=lambda: client)
        supervisor.start()
        supervisor.stop(timeout=2)
        client.shutdown.assert_called_once_with()

    def test_restart_replaces_the_process(self):
        supervisor = self.build()
        first = supervisor.start()
        second = supervisor.restart(timeout=2)
        self.assertNotEqual(first, second)
        self.assertTrue(supervisor._pid_alive(second))
        self.assertFalse(supervisor._pid_alive(first))

    def test_cleanup_stops_the_child(self):
        supervisor = self.build()
        pid = supervisor.start()
        supervisor.cleanup()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and supervisor._pid_alive(pid):
            time.sleep(0.1)
        self.assertFalse(supervisor._pid_alive(pid))

    def test_start_without_a_command_is_reported(self):
        config = dict(self.config)
        config["service"] = {"command": [], "cwd": None, "env": {}}
        supervisor = ServiceSupervisor(
            config, state_dir=self.tmp.name
        )
        with self.assertRaises(ToneyError):
            supervisor.start()

    def test_service_command_appends_the_config_path(self):
        supervisor = self.build()
        command = supervisor.service_command()
        self.assertEqual(command[-2:], ["--config", "/etc/toney/dnsguard.json"])

    def test_service_command_keeps_an_explicit_config_flag(self):
        config = dict(self.config)
        config["service"] = {"command": ["dnsguard", "serve", "--config", "/tmp/other.json"],
                             "cwd": None, "env": {}}
        supervisor = ServiceSupervisor(config, state_dir=self.tmp.name)
        self.assertEqual(supervisor.service_command(),
                         ["dnsguard", "serve", "--config", "/tmp/other.json"])

    def test_service_command_without_a_config_path(self):
        config = dict(self.config)
        config["config_path"] = None
        supervisor = ServiceSupervisor(config, state_dir=self.tmp.name)
        self.assertEqual(supervisor.service_command(), list(DUMMY_COMMAND))

    def test_manager_command_is_read_from_the_configuration(self):
        config = dict(self.config)
        config["service"] = {
            "command": list(DUMMY_COMMAND),
            "cwd": None,
            "env": {},
            "manager": {"start": ["launchctl", "kickstart", "gui/501/x"]},
        }
        supervisor = ServiceSupervisor(config, state_dir=self.tmp.name)
        self.assertEqual(supervisor.manager_command("start"),
                         ["launchctl", "kickstart", "gui/501/x"])
        self.assertEqual(supervisor.manager_command("stop"), [])

    def test_start_asks_the_manager_instead_of_spawning(self):
        calls = []
        config = dict(self.config)
        config["service"] = {
            "command": list(DUMMY_COMMAND),
            "cwd": None,
            "env": {},
            "manager": {"start": ["true"]},
        }
        supervisor = ServiceSupervisor(config, state_dir=self.tmp.name)
        supervisor._run_manager = lambda command: calls.append(command) or True
        supervisor.start()
        self.assertEqual(calls, [["true"]])
        self.assertIsNone(supervisor._child)

    def test_start_reports_a_manager_that_refuses(self):
        config = dict(self.config)
        config["service"] = {
            "command": list(DUMMY_COMMAND),
            "cwd": None,
            "env": {},
            "manager": {"start": ["false"]},
        }
        supervisor = ServiceSupervisor(config, state_dir=self.tmp.name)
        with self.assertRaises(ToneyError):
            supervisor.start()

    def test_restart_asks_the_manager_when_one_is_configured(self):
        calls = []
        config = dict(self.config)
        config["service"] = {
            "command": list(DUMMY_COMMAND),
            "cwd": None,
            "env": {},
            "manager": {"restart": ["true"]},
        }
        supervisor = ServiceSupervisor(config, state_dir=self.tmp.name)
        supervisor._run_manager = lambda command: calls.append(command) or True
        supervisor.restart(timeout=1)
        self.assertEqual(calls, [["true"]])
        self.assertIsNone(supervisor._child)


if __name__ == "__main__":
    unittest.main()

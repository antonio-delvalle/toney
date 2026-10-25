"""Tests for the Toney configuration file handling."""

import json
import os
import tempfile
import unittest

import support
from toney.config import DEFAULTS, load_config, save_config


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "toney.json")

    def test_missing_file_returns_the_defaults(self):
        config = load_config(os.path.join(self.tmp.name, "absent.json"))
        self.assertEqual(config["control_socket"], os.path.expanduser(DEFAULTS["control_socket"]))
        self.assertEqual(
            config["service"]["command"], DEFAULTS["service"]["command"]
        )
        self.assertEqual(config["config_path"], DEFAULTS["config_path"])

    def test_broken_file_returns_the_defaults(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        config = load_config(self.path)
        self.assertEqual(config["config_path"], DEFAULTS["config_path"])

    def test_save_and_load_round_trip(self):
        config = load_config(self.path)
        config["control_socket"] = os.path.join(self.tmp.name, "custom.sock")
        config["service"]["command"] = ["python3", "-m", "dnsguard", "serve", "--verbose"]
        config["service"]["env"] = {"TONEY_TEST": "1"}
        config["service"]["cwd"] = os.path.join(self.tmp.name, "work")
        saved = save_config(config, self.path)
        self.assertTrue(os.path.isfile(saved))
        loaded = load_config(self.path)
        self.assertEqual(loaded["control_socket"], config["control_socket"])
        self.assertEqual(loaded["service"]["command"], config["service"]["command"])
        self.assertEqual(loaded["service"]["env"], {"TONEY_TEST": "1"})
        self.assertEqual(loaded["service"]["cwd"], config["service"]["cwd"])

    def test_partial_file_is_merged_with_the_defaults(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"service": {"command": ["dnsguard"]}}, handle)
        config = load_config(self.path)
        self.assertEqual(config["service"]["command"], ["dnsguard"])
        self.assertEqual(config["config_path"], DEFAULTS["config_path"])
        self.assertIn("env", config["service"])

    def test_the_service_manager_survives_normalisation(self):
        manager = {"start": ["launchctl", "kickstart", "gui/501/x"]}
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"service": {"manager": manager}}, handle)
        config = load_config(self.path)
        self.assertEqual(config["service"]["manager"]["start"], manager["start"])

    def test_the_service_manager_is_empty_by_default(self):
        config = load_config(self.path)
        self.assertEqual(config["service"]["manager"], {})

    def test_user_home_is_expanded(self):
        config = load_config(self.path)
        self.assertFalse(config["control_socket"].startswith("~"))
        self.assertTrue(os.path.isabs(config["control_socket"]))

    def test_save_creates_the_parent_directory(self):
        target = os.path.join(self.tmp.name, "nested", "dir", "toney.json")
        save_config(load_config(target), target)
        self.assertTrue(os.path.isfile(target))

    def test_the_client_names_are_read(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"clients": {"192.0.2.10": "living-room-tv"}}, handle)
        config = load_config(self.path)
        self.assertEqual(config["clients"], {"192.0.2.10": "living-room-tv"})

    def test_the_client_names_are_empty_by_default(self):
        config = load_config(self.path)
        self.assertEqual(config["clients"], {})

    def test_broken_client_names_are_dropped(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"clients": {"192.0.2.10": "", "": "tv", "192.0.2.11": 7}}, handle)
        config = load_config(self.path)
        self.assertEqual(config["clients"], {"192.0.2.11": "7"})

    def test_client_names_that_are_not_a_mapping_are_ignored(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"clients": ["192.0.2.10"]}, handle)
        config = load_config(self.path)
        self.assertEqual(config["clients"], {})


if __name__ == "__main__":
    unittest.main()

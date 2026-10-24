import json
import os
import tempfile
import unittest

from dnsguard.config import Config, default_config


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        config = Config()
        self.assertEqual(config.get("retention_days"), 5)
        self.assertEqual(config.get("log_max_bytes"), 64 * 1024 * 1024)
        self.assertTrue(config.get("listen"))

    def test_default_config_has_upstream_from_system(self):
        self.assertIsInstance(default_config()["upstream"], list)

    def test_load_and_save_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "nested", "dnsguard.json")
            config = Config({"upstream": ["192.0.2.53"], "retention_days": 3})
            config.save(path)
            loaded = Config.load(path)
        self.assertEqual(loaded.get("upstream"), ["192.0.2.53"])
        self.assertEqual(loaded.get("retention_days"), 3)

    def test_load_missing_file_returns_defaults(self):
        config = Config.load("/nonexistent/dnsguard.json")
        self.assertEqual(config.get("retention_days"), 5)

    def test_load_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "bad.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not json")
            with self.assertRaises(ValueError):
                Config.load(path)

    def test_apply_reports_changes(self):
        config = Config()
        changed = config.apply({"retention_days": 2})
        self.assertEqual(changed, ["retention_days"])
        self.assertEqual(config.get("retention_days"), 2)

    def test_apply_ignores_unchanged_values(self):
        config = Config({"retention_days": 2})
        self.assertEqual(config.apply({"retention_days": 2}), [])

    def test_apply_rejects_unknown_setting(self):
        with self.assertRaises(ValueError):
            Config().apply({"nonsense": 1})

    def test_apply_rejects_wrong_type(self):
        with self.assertRaises(ValueError):
            Config().apply({"upstream": "192.0.2.53"})

    def test_apply_rejects_control_path(self):
        with self.assertRaises(ValueError):
            Config().apply({"control": "/tmp/x.sock"})

    def test_validate(self):
        self.assertTrue(Config().validate())

    def test_validate_rejects_bad_listen(self):
        with self.assertRaises(ValueError):
            Config({"listen": "nonsense"}).validate()

    def test_validate_rejects_bad_retention(self):
        with self.assertRaises(ValueError):
            Config({"retention_days": 0}).validate()

    def test_expanded_paths(self):
        config = Config({"log_dir": "~/logs"})
        self.assertTrue(config.expanded("log_dir").startswith(os.path.expanduser("~")))

    def test_save_writes_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "c.json")
            Config({"upstream": ["192.0.2.53"]}).save(path)
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        self.assertEqual(data["upstream"], ["192.0.2.53"])


if __name__ == "__main__":
    unittest.main()

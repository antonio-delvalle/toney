"""Tests for the rules editor and the router view."""

import os
import unittest

import support
from textual.widgets import DataTable
from toney.views.router import RouterView
from toney.views.rules import RulesView


class RulesEditorTests(support.AppTestCase):
    """The rules view edits the rule file and asks the service to reload it."""

    responses = {
        "rules.list": {
            "count": 2,
            "rules": [
                {"pattern": "||ads.example.net^", "action": "block", "source": "a", "line": 1},
                {"pattern": "||cdn.example.net^", "action": "allow", "source": "a", "line": 2},
            ],
        },
        "rules.set": {"count": 3, "loaded_at": "2026-01-02T03:04:05Z"},
    }

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.rules_file = os.path.join(self.tmp.name, "rules.blocklist")
        self.config["rules_file"] = self.rules_file
        self.view = self.app.screen.query_one("#rules", RulesView)
        self.view.load_data()

    def answer(self, value):
        self.app.prompt_for = lambda label, initial, callback: callback(value)

    def read_rules_file(self):
        with open(self.rules_file, encoding="utf-8") as handle:
            return handle.read()

    async def test_add_block_rule(self):
        self.answer("tracker.example.net")
        self.view.add_rule("block")
        content = self.read_rules_file()
        self.assertIn("||tracker.example.net^", content)
        self.assertIn("||ads.example.net^", content)
        self.assertIn("@@||cdn.example.net^", content)

    async def test_add_keep_rule(self):
        self.answer("static.example.net")
        self.view.add_rule("allow")
        self.assertIn("@@||static.example.net^", self.read_rules_file())

    async def test_invalid_domain_is_rejected(self):
        self.answer("not a domain")
        self.view.add_rule("block")
        self.assertFalse(os.path.exists(self.rules_file))
        self.assertEqual(self.app.status_kind, "error")

    async def test_rules_set_is_sent_to_the_service(self):
        self.answer("tracker.example.net")
        self.view.add_rule("block")
        commands = [cmd for cmd, _ in self.client.requests]
        self.assertIn("rules.set", commands)

    async def test_delete_removes_the_selected_rule(self):
        self.view.query_one("#rules", DataTable).move_cursor(row=0)
        self.view.delete_selected()
        content = self.read_rules_file()
        self.assertNotIn("||ads.example.net^", content)
        self.assertIn("||cdn.example.net^", content)

    async def test_delete_without_rules_fails(self):
        self.view.rules = []
        self.view.delete_selected()
        self.assertEqual(self.app.status_kind, "error")

    async def test_delete_with_a_search_removes_the_matching_rule(self):
        self.view.search = "cdn"
        self.view._fill_rules()
        self.view.query_one("#rules", DataTable).move_cursor(row=0)
        self.view.delete_selected()
        content = self.read_rules_file()
        self.assertNotIn("||cdn.example.net^", content)
        self.assertIn("||ads.example.net^", content)

    async def test_delete_with_a_search_keeps_the_other_rules(self):
        self.view.search = "ads"
        self.view._fill_rules()
        self.view.query_one("#rules", DataTable).move_cursor(row=0)
        self.view.delete_selected()
        content = self.read_rules_file()
        self.assertNotIn("||ads.example.net^", content)
        self.assertIn("||cdn.example.net^", content)

    async def test_the_search_narrows_the_table(self):
        self.view.search = "cdn"
        self.view._fill_rules()
        table = self.view.query_one("#rules", DataTable)
        self.assertEqual(table.row_count, 1)

    async def test_rule_text_keeps_the_allow_marker(self):
        text = self.view.rule_text(self.view.rules)
        self.assertIn("@@||cdn.example.net^", text)

    async def test_the_keys_reach_the_view(self):
        self.assertTrue(self.view.handle_char("a"))
        self.assertTrue(self.view.handle_char("k"))
        self.assertTrue(self.view.handle_char("d"))
        self.assertFalse(self.view.handle_char("z"))


class RouterViewTests(support.AppTestCase):
    """The router view deploys the rule set to the router."""

    responses = {
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
    }

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.view = self.app.screen.query_one("#router", RouterView)
        self.view.load_data()

    async def test_the_status_is_read(self):
        self.assertTrue(self.view.state["configured"])

    async def test_deploy_calls_the_service(self):
        self.view.deploy()
        commands = [cmd for cmd, _ in self.client.requests]
        self.assertIn("router.deploy", commands)

    async def test_rollback_calls_the_service(self):
        self.view.rollback()
        commands = [cmd for cmd, _ in self.client.requests]
        self.assertIn("router.rollback", commands)

    async def test_the_keys_are_handled(self):
        self.assertTrue(self.view.handle_char("d"))
        self.assertTrue(self.view.handle_char("b"))
        self.assertFalse(self.view.handle_char("z"))


if __name__ == "__main__":
    unittest.main()

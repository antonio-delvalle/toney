"""Tests for the Textual interface of Toney."""

import os
import re
import tempfile
import unittest

import support
from toney.client import ServiceUnreachable
from toney.controller import ToneyController
from toney.devices import DeviceResolver
from toney.theme import COLORS, TOKYO_NIGHT, TONEY_LIGHT
from toney.views.base import (
    client_cell,
    decision_cell,
    device_cell,
    summary_card,
)
from textual.widgets import ContentSwitcher


class ControllerTest(unittest.TestCase):
    """The controller holds everything that does not need a terminal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.socket = os.path.join(self.tmp.name, "dnsguard.sock")
        self.client = support.FakeClient({"status": {"name": "dnsguard"}})
        self.controller = ToneyController(
            {"control_socket": self.socket},
            client_factory=lambda: self.client,
        )

    def test_a_socket_error_becomes_a_status_message(self):
        client = support.FakeClient({"status": ServiceUnreachable("no socket")})
        controller = ToneyController(
            {"control_socket": self.socket},
            client_factory=lambda: client,
        )
        self.assertIsNone(controller.request("status"))
        self.assertEqual(controller.status_kind, "error")
        self.assertIn("no socket", controller.status_message)

    def test_the_service_state_follows_the_socket(self):
        self.assertEqual(self.controller.service_state(), "stopped")
        self.controller.request("status")
        self.assertEqual(self.controller.service_state(), "running")

    def test_the_status_callback_is_called(self):
        seen = []
        controller = ToneyController(
            {"control_socket": self.socket},
            client_factory=lambda: self.client,
            on_status=lambda message, kind: seen.append((message, kind)),
        )
        controller.set_status("hello", "info")
        self.assertEqual(seen, [("hello", "info")])


class AppTest(support.AppTestCase):
    """The interface, driven by the Textual test driver."""

    responses = {"status": {"name": "dnsguard", "pid": 42}}

    async def test_the_views_are_available(self):
        switcher = self.app.screen.query_one("#views", ContentSwitcher)
        self.assertEqual(
            [child.id for child in switcher.children],
            ["dashboard", "logs", "rules", "service", "router"],
        )

    async def test_a_number_key_switches_the_view(self):
        await self.pilot.press("3")
        self.assertEqual(self.app.view_index, 2)
        self.assertEqual(self.app.current_view.id, "rules")

    async def test_tab_switches_to_the_next_view(self):
        await self.pilot.press("tab")
        self.assertEqual(self.app.view_index, 1)
        await self.pilot.press("shift+tab")
        self.assertEqual(self.app.view_index, 0)

    async def test_the_service_state_is_shown(self):
        await self.pilot.pause()
        self.assertEqual(self.app.service_state, "running")

    async def test_a_socket_error_does_not_break_the_application(self):
        self.client.responses["status"] = ServiceUnreachable("no socket")
        await self.pilot.press("g")
        await self.pilot.pause()
        self.assertEqual(self.app.status_kind, "error")
        self.assertIn("no socket", self.app.status_message)
        self.assertTrue(self.app.is_running)

    async def test_the_help_overlay_opens_and_closes(self):
        await self.pilot.press("?")
        await self.pilot.pause()
        self.assertEqual(type(self.app.screen).__name__, "HelpScreen")
        await self.pilot.press("escape")
        await self.pilot.pause()
        self.assertEqual(type(self.app.screen).__name__, "ToneyScreen")

    async def test_the_config_editor_is_opened(self):
        self.client.responses["config.get"] = {"listen": "0.0.0.0:5353"}
        await self.pilot.press("c")
        await self.pilot.pause()
        self.assertEqual(type(self.app.screen).__name__, "ConfigEditorScreen")
        self.assertIn(("config.get", {}), self.client.requests)

    async def test_quit_stops_the_application(self):
        await self.pilot.press("q")
        await self.pilot.pause()
        self.assertFalse(self.app.is_running)

    async def test_the_dashboard_lists_the_clients(self):
        self.client.responses["status"] = {
            "name": "dnsguard",
            "clients": {"192.0.2.10": {"total": 3, "allowed": 2, "blocked": 1}},
        }
        await self.pilot.press("g")
        await self.pilot.pause()
        table = self.app.screen.query_one("#clients")
        self.assertEqual(table.row_count, 1)
        self.assertEqual(str(table.get_row_at(0)[1]), "192.0.2.10")

    async def test_the_dashboard_has_three_sections(self):
        await self.pilot.pause()
        view = self.app.screen.query_one("#dashboard")
        self.assertEqual(
            [child.id for child in view.children],
            ["cards", None, "clients", None, "recent-logs"],
        )

    async def test_the_cards_are_side_by_side(self):
        await self.pilot.pause()
        cards = self.app.screen.query_one("#cards")
        self.assertEqual(len(cards.children), 4)
        self.assertEqual(
            [child.id for child in cards.children],
            ["card-service", "card-counters", "card-rules", "card-logs"],
        )
        self.assertEqual(len({card.region.y for card in cards.children}), 1)
        self.assertEqual(len({card.region.x for card in cards.children}), 4)


class CardTest(unittest.TestCase):
    """The summary cards keep one line per row, whatever the width."""

    def test_a_card_writes_a_label_and_a_value(self):
        card = summary_card("Service", [("state", "running")])
        self.assertEqual(card.plain, "Service\nstate running\n")

    def test_a_long_value_is_cut(self):
        card = summary_card("Service", [("listen", "0.0.0.0:5353")], 12)
        self.assertEqual(card.plain, "Service\nlisten 0.0.…\n")

    def test_the_labels_are_in_a_column(self):
        card = summary_card(
            "Counters", [("total", 18422), ("allowed", 15412)], 14
        )
        self.assertEqual(
            card.plain.splitlines()[1:], ["total   18422", "allowed 15412"]
        )

    def test_a_label_keeps_its_space(self):
        card = summary_card(
            "Service", [("version", "0.1.0"), ("state", "running")], 16
        )
        self.assertEqual(
            card.plain.splitlines()[1:], ["version 0.1.0", "state   running"]
        )


class CellTest(unittest.TestCase):
    """The cells of the log tables."""

    def test_the_client_cell_carries_the_device_name(self):
        cell = client_cell("192.0.2.10", {"192.0.2.10": "living-room-tv"})
        self.assertEqual(str(cell), "living-room-tv  192.0.2.10")

    def test_an_unknown_client_is_shown_on_its_own(self):
        cell = client_cell("192.0.2.10", {})
        self.assertEqual(str(cell), "192.0.2.10")

    def test_a_client_without_a_name_is_shown_on_its_own(self):
        cell = client_cell("192.0.2.10", {"192.0.2.10": ""})
        self.assertEqual(str(cell), "192.0.2.10")

    def test_the_device_cell_of_an_unknown_device_is_a_dash(self):
        self.assertEqual(str(device_cell("")), "-")

    def test_a_blocked_decision_is_red(self):
        self.assertEqual(decision_cell("block").style, COLORS["block"])

    def test_an_allowed_decision_is_green(self):
        self.assertEqual(decision_cell("allow").style, COLORS["ok"])

    def test_a_cached_decision_is_green(self):
        self.assertEqual(decision_cell("cache").style, COLORS["ok"])


class DeviceSweepTest(support.AppTestCase):
    """The sweep finds the names of the devices behind the addresses."""

    responses = {
        "status": {"name": "dnsguard", "clients": {"192.0.2.10": {"total": 3}}},
        "logs.clients": {"clients": ["192.0.2.10"]},
    }

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.app.controller.devices.lookup = lambda address: "living-room-tv"

    def _sweeps(self):
        return len([c for c, _p in self.client.requests if c == "logs.clients"])

    async def _wait_for_names(self):
        for _ in range(100):
            await self.pilot.pause(0.02)
            if self.app.controller.device_names():
                return
        self.fail("the sweep did not find any name")

    async def test_the_d_key_sweeps_the_log(self):
        before = self._sweeps()
        await self.pilot.press("d")
        await self._wait_for_names()
        self.assertGreater(self._sweeps(), before)

    async def test_the_sweep_finds_the_names(self):
        self.app.controller.devices = DeviceResolver(
            lookup=lambda address: "living-room-tv"
        )
        await self.pilot.press("d")
        await self._wait_for_names()
        self.assertEqual(
            self.app.controller.device_names(), {"192.0.2.10": "living-room-tv"}
        )

    async def test_the_names_show_in_the_dashboard(self):
        await self.pilot.press("d")
        await self._wait_for_names()
        await self.pilot.pause()
        table = self.app.screen.query_one("#clients")
        self.assertEqual(str(table.get_row_at(0)[0]), "living-room-tv")

    async def test_the_configuration_wins_over_the_lookup(self):
        self.app.controller.config["clients"] = {"192.0.2.10": "the-tv"}
        await self.pilot.press("d")
        await self._wait_for_names()
        self.assertEqual(
            self.app.controller.device_names(), {"192.0.2.10": "the-tv"}
        )

    async def test_the_rules_view_keeps_the_d_key(self):
        await self.pilot.press("3")
        await self.pilot.pause()
        before = self._sweeps()
        await self.pilot.press("d")
        await self.pilot.pause()
        self.assertEqual(self._sweeps(), before)


class ThemeAppTest(support.AppTestCase):
    """The theme on the screen reaches the text as well as the stylesheet."""

    records = [
        {
            "ts": "2026-10-24T09:02:01Z",
            "client": "192.0.2.10",
            "name": "ads.example.com.",
            "type": "A",
            "decision": "block",
            "rule": "||ads.example.com^",
        }
    ]

    responses = {
        "status": {"name": "dnsguard"},
        "logs.tail": {"lines": records},
    }

    async def test_the_app_starts_on_the_tokyo_night_theme(self):
        await self.pilot.pause()
        self.assertEqual(self.app.theme, "tokyo-night")

    async def test_the_decision_uses_the_colours_of_the_theme(self):
        await self.pilot.pause()
        table = self.app.screen.query_one("#recent-logs")
        self.assertEqual(table.get_row_at(0)[3].style, TOKYO_NIGHT["block"])

    async def test_a_change_of_theme_draws_the_text_again(self):
        await self.pilot.pause()
        self.app.theme = "toney-light"
        await self.pilot.pause()
        table = self.app.screen.query_one("#recent-logs")
        self.assertEqual(table.get_row_at(0)[3].style, TONEY_LIGHT["block"])


class LogTableTest(support.AppTestCase):
    """The log tables show the time, the client, the name, the decision and the rule."""

    records = [
        {
            "ts": "2026-10-24T09:02:01Z",
            "client": "192.0.2.10",
            "name": "ads.example.com.",
            "type": "A",
            "decision": "block",
            "rule": "||ads.example.com^",
        },
        {
            "ts": "2026-10-24T09:02:02Z",
            "client": "192.0.2.10",
            "name": "example.com.",
            "type": "A",
            "decision": "cache",
            "rule": None,
        },
    ]

    responses = {
        "status": {"name": "dnsguard"},
        "logs.tail": {"lines": records},
    }

    extra_config = {"clients": {"192.0.2.10": "living-room-tv"}}

    async def test_the_type_column_is_gone(self):
        await self.pilot.press("2")
        await self.pilot.pause()
        table = self.app.screen.query_one("#records")
        self.assertEqual(
            [str(column.label) for column in table.columns.values()],
            ["timestamp", "client", "name", "decision", "rule"],
        )

    async def test_the_client_column_carries_the_device_name(self):
        await self.pilot.press("2")
        await self.pilot.pause()
        table = self.app.screen.query_one("#records")
        cell = str(table.get_row_at(0)[1])
        self.assertIn("living-room-tv", cell)
        self.assertIn("192.0.2.10", cell)
        self.assertLess(cell.index("living-room-tv"), cell.index("192.0.2.10"))

    async def test_the_decision_is_coloured(self):
        await self.pilot.press("2")
        await self.pilot.pause()
        table = self.app.screen.query_one("#records")
        self.assertEqual(table.get_row_at(0)[3].style, COLORS["block"])
        self.assertEqual(table.get_row_at(1)[3].style, COLORS["ok"])

    async def test_the_timestamp_is_readable(self):
        await self.pilot.press("2")
        await self.pilot.pause()
        table = self.app.screen.query_one("#records")
        cell = str(table.get_row_at(0)[0])
        self.assertNotEqual(cell, "2026-10-24T09:02:01Z")
        self.assertRegex(cell, r"^[A-Z][a-z]+ [A-Z][a-z]+ \d{2}, \d{2}:\d{2}:\d{2}$")

    async def test_the_dashboard_shows_the_recent_logs(self):
        await self.pilot.pause()
        table = self.app.screen.query_one("#recent-logs")
        self.assertEqual(table.row_count, 2)
        self.assertEqual(str(table.get_row_at(0)[2]), "ads.example.com.")
        self.assertEqual(str(table.get_row_at(0)[4]), "||ads.example.com^")

    async def test_the_dashboard_names_the_clients(self):
        self.client.responses["status"] = {
            "name": "dnsguard",
            "clients": {"192.0.2.10": {"total": 3, "allowed": 2, "blocked": 1}},
        }
        await self.pilot.press("g")
        await self.pilot.pause()
        table = self.app.screen.query_one("#clients")
        self.assertEqual(str(table.get_row_at(0)[0]), "living-room-tv")
        self.assertEqual(str(table.get_row_at(0)[1]), "192.0.2.10")


if __name__ == "__main__":
    unittest.main()

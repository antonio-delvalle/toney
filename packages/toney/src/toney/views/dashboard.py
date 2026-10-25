"""Dashboard view: overall state of the dnsguard service."""

from __future__ import annotations

from typing import Any, Dict, List

from textual.app import ComposeResult
from textual.containers import Grid
from textual.widgets import DataTable, Static

from toney.formatting import format_bytes, format_duration, format_time
from toney.views.base import LOG_COLUMNS, ToneyView, device_cell, log_row, summary_card

RECENT_LOGS = 20


class DashboardView(ToneyView):
    """Shows the service state, counters, clients and the most recent logs."""

    name = "dashboard"
    title = "Dashboard"

    def compose(self) -> ComposeResult:
        with Grid(id="cards"):
            yield Static(id="card-service", classes="card")
            yield Static(id="card-counters", classes="card")
            yield Static(id="card-rules", classes="card")
            yield Static(id="card-logs", classes="card")
        yield Static("Clients", classes="section-title")
        yield DataTable(id="clients")
        yield Static("Recent logs", classes="section-title")
        yield DataTable(id="recent-logs")

    def on_mount(self) -> None:
        clients = self.query_one("#clients", DataTable)
        clients.add_columns("device", "client", "total", "allowed", "blocked")
        clients.cursor_type = "row"
        logs = self.query_one("#recent-logs", DataTable)
        logs.add_columns(*LOG_COLUMNS)
        logs.cursor_type = "row"

    def load_data(self) -> None:
        if not self.is_mounted:
            return
        data = self.controller.request("status")
        if data is None:
            self._set_card("card-service", "Service", [("state", self.controller.service_state())])
            self._set_card("card-counters", "Counters", [])
            self._set_card("card-rules", "Rules", [])
            self._set_card("card-logs", "Logs", [])
            self._fill_clients({})
            self._fill_logs([])
            return
        self.data = data
        counters = data.get("counters") or {}
        rules = data.get("rules") or {}
        log = data.get("log") or {}

        self._set_card(
            "card-service",
            "Service",
            [
                ("state", self.controller.service_state()),
                ("name", data.get("name", "-")),
                ("version", data.get("version", "-")),
                ("pid", data.get("pid", "-")),
                ("uptime", format_duration(data.get("uptime_s"))),
                ("listen", data.get("listen", "-")),
            ],
        )
        self._set_card(
            "card-counters",
            "Counters",
            [
                ("total", counters.get("total", 0)),
                ("allowed", counters.get("allowed", 0)),
                ("blocked", counters.get("blocked", 0)),
                ("cached", counters.get("cached", 0)),
                ("errors", counters.get("errors", 0)),
            ],
        )
        sources: List[str] = list(rules.get("sources") or [])
        self._set_card(
            "card-rules",
            "Rules",
            [
                ("count", rules.get("count", 0)),
                ("block", rules.get("block", 0)),
                ("allow", rules.get("allow", 0)),
                ("files", len(sources)),
                ("loaded", format_time(rules.get("loaded_at"))),
            ],
        )
        self._set_card(
            "card-logs",
            "Logs",
            [
                ("dir", _basename(log.get("dir"))),
                ("files", len(log.get("files") or [])),
                ("size", format_bytes(log.get("total_bytes"))),
                ("keep", "{0} day(s)".format(log.get("retention_days", "-"))),
            ],
        )
        self._fill_clients(data.get("clients") or {})
        self._fill_logs(self._recent_logs())

    def _set_card(self, card_id: str, title: str, rows) -> None:
        self.query_one("#{0}".format(card_id), Static).update(
            summary_card(title, rows, self._card_width(), self.colors)
        )

    def _card_width(self) -> int:
        """The number of columns one card has for its text.

        A card is a quarter of the grid, less its border, its padding and the
        margin that keeps it away from the next one.
        """
        width = self.content_size.width or self.size.width
        if not width:
            return 40
        return max(8, width // 4 - 5)

    def _recent_logs(self) -> List[dict]:
        data = self.controller.request("logs.tail", {"limit": RECENT_LOGS})
        if data is None:
            return []
        return list(data.get("lines") or [])[:RECENT_LOGS]

    def _fill_clients(self, clients: Dict[str, Any]) -> None:
        table = self.query_one("#clients", DataTable)
        table.clear()
        names = self.device_names()
        for client in sorted(clients.keys()):
            entry = clients[client] or {}
            table.add_row(
                device_cell(names.get(str(client), ""), self.colors),
                str(client),
                str(entry.get("total", 0)),
                str(entry.get("allowed", 0)),
                str(entry.get("blocked", 0)),
            )

    def _fill_logs(self, records: List[dict]) -> None:
        table = self.query_one("#recent-logs", DataTable)
        table.clear()
        names = self.device_names()
        for record in records:
            table.add_row(*log_row(record, names, self.colors))


def _basename(path) -> str:
    """The last part of a path, so a card does not spend a line on a folder."""
    text = str(path or "-")
    if "/" not in text:
        return text
    return text.rstrip("/").rsplit("/", 1)[-1] or text

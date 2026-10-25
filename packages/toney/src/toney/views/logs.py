"""Logs view: live tail of the query log."""

from __future__ import annotations

from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Static

from toney.views.base import LOG_COLUMNS, ToneyView, log_row

COLUMNS = LOG_COLUMNS


class LogsView(ToneyView):
    """Shows recent query log records with an optional filter."""

    name = "logs"
    title = "Logs"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.text_filter = ""
        self.client_filter = ""
        self.records: List[dict] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="filters"):
            yield Input(placeholder="substring filter", id="text-filter")
            yield Input(placeholder="client filter", id="client-filter")
            yield Button("Apply", id="apply", flat=True)
        yield Static("", id="filter-summary", classes="section-title")
        yield DataTable(id="records")

    def on_mount(self) -> None:
        table = self.query_one("#records", DataTable)
        table.add_columns(*COLUMNS)
        table.cursor_type = "row"

    def search_input(self) -> Optional[Input]:
        return self.query_one("#text-filter", Input)

    def load_data(self) -> None:
        if not self.is_mounted:
            return
        params = {"limit": 500}
        if self.text_filter:
            params["filter"] = self.text_filter
        if self.client_filter:
            params["client"] = self.client_filter
        data = self.controller.request("logs.tail", params)
        if data is None:
            return
        self.data = data
        self.records = list(data.get("lines") or [])
        self._fill_records()

    def _fill_records(self) -> None:
        table = self.query_one("#records", DataTable)
        table.clear()
        names = self.device_names()
        for record in self.records:
            table.add_row(*log_row(record, names, self.colors))
        summary = "filter: {0}".format(self.text_filter or "(none)")
        if self.client_filter:
            summary += "    client: {0}".format(self.client_filter)
        summary += "    {0} record(s)".format(len(self.records))
        self.query_one("#filter-summary", Static).update(summary)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._read_filters()
        self.load_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply":
            self._read_filters()
            self.load_data()

    def _read_filters(self) -> None:
        self.text_filter = self.query_one("#text-filter", Input).value.strip()
        self.client_filter = self.query_one("#client-filter", Input).value.strip()

    def handle_char(self, char: str) -> bool:
        if char == "F":
            self.query_one("#client-filter", Input).focus()
            return True
        return False

"""Logs view: live tail of the query log."""

from __future__ import annotations

from toney.term import curses
from typing import List, Optional

from toney.views.base import View
from toney.widgets import Rect, render_table, safe_addstr


class LogsView(View):
    """Shows recent query log records with an optional filter."""

    name = "logs"
    title = "Logs"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.text_filter = ""
        self.client_filter = ""
        self.records: List[dict] = []
        self.scroll = 0

    def refresh(self) -> None:
        params = {"limit": 500}
        if self.text_filter:
            params["filter"] = self.text_filter
        if self.client_filter:
            params["client"] = self.client_filter
        data = self.app.request("logs.tail", params)
        if data is not None:
            self.data = data
            self.records = list(data.get("lines") or [])
            self.scroll = 0

    def visible_records(self) -> List[dict]:
        return self.records

    def render(self, window, rect: Rect) -> None:
        top, left, height, width = rect
        filters = "filter: {0}".format(self.text_filter or "(none)")
        if self.client_filter:
            filters += "   client: {0}".format(self.client_filter)
        safe_addstr(window, top, left, filters, curses.A_DIM)
        row = top + 1
        records = self.visible_records()
        if not records:
            safe_addstr(window, row, left, "No log records match the current filter.")
            return
        rows = []
        for record in records:
            rows.append(
                [
                    str(record.get("ts", "")),
                    str(record.get("client", "")),
                    str(record.get("name", "")),
                    str(record.get("type", "")),
                    str(record.get("decision", "")),
                    str(record.get("rule", "")),
                ]
            )
        body_height = max(1, height - 2)
        if self.scroll > max(0, len(rows) - body_height):
            self.scroll = max(0, len(rows) - body_height)
        window_rows = rows[self.scroll : self.scroll + body_height]
        render_table(
            window,
            row,
            left,
            width,
            ["timestamp", "client", "name", "type", "decision", "rule"],
            window_rows,
            weights=[2, 2, 3, 1, 1, 2],
        )

    def handle_key(self, key: int) -> bool:
        if key == ord("/"):
            value = self.app.prompt("Substring filter: ", self.text_filter)
            if value is not None:
                self.text_filter = value.strip()
                self.app.refresh_view(self)
            return True
        if key == ord("F"):
            value = self.app.prompt("Client filter: ", self.client_filter)
            if value is not None:
                self.client_filter = value.strip()
                self.app.refresh_view(self)
            return True
        if key == curses.KEY_DOWN:
            self.scroll += 1
            return True
        if key == curses.KEY_UP:
            self.scroll = max(0, self.scroll - 1)
            return True
        if key == curses.KEY_NPAGE:
            self.scroll += 10
            return True
        if key == curses.KEY_PPAGE:
            self.scroll = max(0, self.scroll - 10)
            return True
        if key == curses.KEY_HOME:
            self.scroll = 0
            return True
        return False

"""Configuration editor overlay.

The editor changes the service configuration through the ``config.set``
command.  Only the documented keys are touched: ``listen``, ``upstream``,
``log_dir`` and ``retention_days``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from toney.term import curses
from toney.widgets import safe_addstr


class ConfigEditor:
    """A small modal form for the runtime configuration of the service."""

    def __init__(self, app: Any, values: Dict[str, Any]) -> None:
        self.app = app
        self.values = values or {}
        self.items: List[List[str]] = [
            ["listen", str(self.values.get("listen", "")), "address to bind the DNS socket to"],
            [
                "upstream",
                ", ".join(str(part) for part in (self.values.get("upstream") or [])),
                "comma separated list of upstream resolvers",
            ],
            ["log_dir", str(self.values.get("log_dir", "")), "directory the query log is written to"],
            [
                "retention_days",
                str(self.values.get("retention_days", "")),
                "number of days the query log is kept",
            ],
        ]
        self.index = 0
        self.cursor = len(self.items[0][1])
        self.closed = False

    def current(self) -> List[str]:
        return self.items[self.index]

    def render(self, window) -> None:
        maxy, maxx = window.getmaxyx()
        width = min(maxx - 4, 74)
        height = len(self.items) + 6
        top = max(0, (maxy - height) // 2)
        left = max(0, (maxx - width) // 2)
        safe_addstr(window, top, left, "+" + "-" * max(0, width - 2) + "+", curses.A_BOLD)
        safe_addstr(window, top + height - 1, left, "+" + "-" * max(0, width - 2) + "+", curses.A_BOLD)
        for offset in range(1, height - 1):
            safe_addstr(window, top + offset, left, "|")
            safe_addstr(window, top + offset, left + width - 1, "|")
        safe_addstr(window, top + 1, left + 2, "Service configuration", curses.A_BOLD)
        row = top + 3
        for index, (name, value, hint) in enumerate(self.items):
            attr = curses.A_BOLD if index == self.index else curses.A_NORMAL
            safe_addstr(window, row, left + 2, name.ljust(16), attr)
            safe_addstr(window, row, left + 18, value.ljust(max(0, width - 22)))
            if index == self.index:
                try:
                    window.move(row, min(left + 18 + self.cursor, maxx - 1))
                except Exception:
                    pass
            row += 1
            safe_addstr(window, row, left + 18, hint, curses.A_DIM)
            row += 1
        safe_addstr(
            window,
            top + height - 2,
            left + 2,
            "Enter next field  F2 apply  Esc cancel",
            curses.A_DIM,
        )

    def move(self, delta: int) -> None:
        self.index = (self.index + delta) % len(self.items)
        self.cursor = len(self.items[self.index][1])

    def apply(self) -> bool:
        params: Dict[str, Any] = {}
        for name, value, _hint in self.items:
            text = value.strip()
            if not text:
                continue
            if name == "upstream":
                servers = [part.strip() for part in text.split(",") if part.strip()]
                params["upstream"] = servers
            elif name == "retention_days":
                try:
                    params["retention_days"] = int(text)
                except ValueError:
                    self.app.set_status("retention days must be a whole number", "error")
                    return False
            else:
                params[name] = text
        if not params:
            self.app.set_status("nothing to apply", "error")
            return False
        result = self.app.request("config.set", params)
        if result is None:
            return False
        self.app.set_status("configuration applied")
        self.closed = True
        return True

    def handle_key(self, key: int) -> bool:
        if key == 27:
            self.app.set_status("configuration edit cancelled")
            self.closed = True
            return True
        if key in (curses.KEY_F2, 19):
            self.apply()
            return self.closed
        if key in (curses.KEY_ENTER, 10, 13):
            if self.index == len(self.items) - 1:
                self.apply()
            else:
                self.move(1)
            return self.closed
        if key in (curses.KEY_DOWN, 9):
            self.move(1)
            return False
        if key == curses.KEY_UP:
            self.move(-1)
            return False
        if key == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
            return False
        if key == curses.KEY_RIGHT:
            self.cursor = min(len(self.current()[1]), self.cursor + 1)
            return False
        if key in (curses.KEY_BACKSPACE, 127, 8):
            item = self.current()
            if self.cursor > 0:
                item[1] = item[1][: self.cursor - 1] + item[1][self.cursor :]
                self.cursor -= 1
            return False
        if key < 32:
            return False
        if 32 <= key < 127:
            item = self.current()
            item[1] = item[1][: self.cursor] + chr(key) + item[1][self.cursor :]
            self.cursor += 1
        return False

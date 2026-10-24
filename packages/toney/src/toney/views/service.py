"""Service view: lifecycle actions for the dnsguard process."""

from __future__ import annotations

from toney.term import curses
from typing import List

from toney.views.base import View
from toney.widgets import Rect, format_duration, safe_addstr

ACTIONS = ("Start", "Stop", "Restart", "Reload rules")


class ServiceView(View):
    """Shows the state of the service and the lifecycle actions."""

    name = "service"
    title = "Service"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.selected = 0

    def refresh(self) -> None:
        data = self.app.request("status")
        if data is not None:
            self.data = data

    def render(self, window, rect: Rect) -> None:
        top, left, height, width = rect
        row = top
        data = self.data or {}
        state = self.app.service_state()
        safe_addstr(window, row, left, "State", curses.A_BOLD)
        row += 1
        safe_addstr(window, row, left, "  state     : {0}".format(state))
        row += 1
        safe_addstr(window, row, left, "  pid       : {0}".format(data.get("pid", "-")))
        row += 1
        safe_addstr(
            window,
            row,
            left,
            "  uptime    : {0}".format(format_duration(data.get("uptime_s"))),
        )
        row += 1
        safe_addstr(window, row, left, "  socket    : {0}".format(self.app.socket_path))
        row += 1
        safe_addstr(window, row, left, "  command   : {0}".format(self.app.service_command()))
        row += 2

        safe_addstr(window, row, left, "Actions", curses.A_BOLD)
        row += 1
        for index, action in enumerate(ACTIONS):
            attr = curses.A_REVERSE if index == self.selected else curses.A_NORMAL
            safe_addstr(window, row, left, "  [{0}] {1}".format(index + 1, action), attr)
            row += 1
        row += 1
        safe_addstr(
            window,
            row,
            left,
            "Use the left and right arrows to pick an action and Enter to run it.",
            curses.A_DIM,
        )
        row += 1
        safe_addstr(
            window,
            row,
            left,
            "Global shortcuts: s start, S stop, r restart, R reload rules.",
            curses.A_DIM,
        )

    def handle_key(self, key: int) -> bool:
        if key == curses.KEY_LEFT:
            self.selected = (self.selected - 1) % len(ACTIONS)
            return True
        if key == curses.KEY_RIGHT:
            self.selected = (self.selected + 1) % len(ACTIONS)
            return True
        if key in (curses.KEY_ENTER, 10, 13):
            self.app.run_action(self.selected)
            return True
        if ord("1") <= key <= ord("4"):
            self.selected = key - ord("1")
            self.app.run_action(self.selected)
            return True
        return False

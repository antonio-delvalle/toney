"""Router view: deploy the rule set to a router that runs dnsmasq."""

from __future__ import annotations

from typing import Any, Dict, List

from toney.term import curses
from toney.views.base import View
from toney.widgets import Rect, safe_addstr


class RouterView(View):
    """Shows the state of the generated rule file on the router."""

    name = "router"
    title = "Router"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.state: Dict[str, Any] = {}
        self.history: List[str] = []

    def refresh(self) -> None:
        data = self.app.request("router.status")
        if data is not None:
            self.data = data
            self.state = dict(data)

    def deploy(self) -> None:
        data = self.app.request("router.deploy")
        if data is None:
            return
        self.history.insert(
            0,
            "deployed {0} rule(s), {1} skipped, {2} byte(s)".format(
                data.get("rules", 0), data.get("skipped", 0), data.get("bytes", 0)
            ),
        )
        self.app.set_status("rule set deployed to the router")
        self.refresh()

    def rollback(self) -> None:
        data = self.app.request("router.rollback")
        if data is None:
            return
        if data.get("removed"):
            message = "the generated file was removed from the router"
        else:
            message = "the previous file was restored"
        self.history.insert(0, message)
        self.app.set_status(message)
        self.refresh()

    def render(self, window, rect: Rect) -> None:
        top, left, height, width = rect
        state = self.state
        if not state.get("configured"):
            safe_addstr(window, top, left, "No router is configured.")
            safe_addstr(
                window,
                top + 1,
                left,
                "Add a \"router\" section to the dnsguard configuration to use this view.",
                curses.A_DIM,
            )
            return
        rows = [
            ("router host", state.get("host")),
            ("remote file", state.get("remote_path")),
            ("installed", "yes" if state.get("installed") else "no"),
            ("matches the loaded rules", "yes" if state.get("matches") else "no"),
            ("remote size", "{0} byte(s)".format(state.get("bytes", 0))),
        ]
        row = top
        for label, value in rows:
            safe_addstr(window, row, left, label.ljust(26), curses.A_BOLD)
            safe_addstr(window, row, left + 26, str(value))
            row += 1
        row += 1
        safe_addstr(
            window,
            row,
            left,
            "[d] deploy the rule set    [b] roll back to the previous file",
            curses.A_DIM,
        )
        row += 2
        for entry in self.history[: max(0, top + height - row - 1)]:
            safe_addstr(window, row, left, entry)
            row += 1

    def handle_key(self, key: int) -> bool:
        if key == ord("d"):
            self.deploy()
            return True
        if key == ord("b"):
            self.rollback()
            return True
        return False

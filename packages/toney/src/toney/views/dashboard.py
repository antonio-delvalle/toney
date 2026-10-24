"""Dashboard view: overall state of the dnsguard service."""

from __future__ import annotations

from toney.term import curses
from typing import Any, Dict, List

from toney.views.base import View
from toney.widgets import Rect, format_bytes, format_duration, render_table, safe_addstr


class DashboardView(View):
    """Shows the service state, counters, clients, upstreams and logs."""

    name = "dashboard"
    title = "Dashboard"

    def refresh(self) -> None:
        data = self.app.request("status")
        if data is not None:
            self.data = data

    def render(self, window, rect: Rect) -> None:
        top, left, height, width = rect
        data = self.data
        if not data:
            safe_addstr(window, top, left, "No status available yet.")
            safe_addstr(window, top + 1, left, "Press 'g' to refresh, 's' to start the service.")
            return
        row = top
        counters = data.get("counters") or {}
        rules = data.get("rules") or {}
        log = data.get("log") or {}
        clients = data.get("clients") or {}

        safe_addstr(window, row, left, "Service", curses.A_BOLD)
        row += 1
        safe_addstr(window, row, left, "  state     : {0}".format(self.app.service_state()))
        row += 1
        safe_addstr(window, row, left, "  name      : {0}".format(data.get("name", "-")))
        row += 1
        safe_addstr(window, row, left, "  version   : {0}".format(data.get("version", "-")))
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
        safe_addstr(window, row, left, "  listen    : {0}".format(data.get("listen", "-")))
        row += 1
        safe_addstr(window, row, left, "  started   : {0}".format(data.get("started_at", "-")))
        row += 1
        safe_addstr(
            window,
            row,
            left,
            "  config    : {0}".format(data.get("config_path", "-")),
        )
        row += 2

        safe_addstr(window, row, left, "Counters", curses.A_BOLD)
        row += 1
        total = counters.get("total", 0)
        allowed = counters.get("allowed", 0)
        blocked = counters.get("blocked", 0)
        cached = counters.get("cached", 0)
        errors = counters.get("errors", 0)
        safe_addstr(
            window,
            row,
            left,
            "  total {0}   allowed {1}   blocked {2}   cached {3}   errors {4}".format(
                total, allowed, blocked, cached, errors
            ),
        )
        row += 2

        safe_addstr(window, row, left, "Upstream servers", curses.A_BOLD)
        row += 1
        upstreams = data.get("upstream") or []
        if upstreams:
            for server in upstreams:
                safe_addstr(window, row, left, "  {0}".format(server))
                row += 1
        else:
            safe_addstr(window, row, left, "  (none)")
            row += 1
        row += 1

        safe_addstr(window, row, left, "Rules", curses.A_BOLD)
        row += 1
        safe_addstr(window, row, left, "  count     : {0}".format(rules.get("count", 0)))
        row += 1
        safe_addstr(window, row, left, "  loaded at : {0}".format(rules.get("loaded_at", "-")))
        row += 1
        sources = rules.get("sources") or []
        if sources:
            for source in sources[:5]:
                safe_addstr(window, row, left, "  source    : {0}".format(source))
                row += 1
        row += 1

        safe_addstr(window, row, left, "Logs", curses.A_BOLD)
        row += 1
        safe_addstr(window, row, left, "  directory : {0}".format(log.get("dir", "-")))
        row += 1
        safe_addstr(
            window,
            row,
            left,
            "  retention : {0} day(s)".format(log.get("retention_days", "-")),
        )
        row += 1
        safe_addstr(
            window,
            row,
            left,
            "  size      : {0} in {1} file(s)".format(
                format_bytes(log.get("total_bytes")), len(log.get("files") or [])
            ),
        )
        row += 2

        safe_addstr(window, row, left, "Clients", curses.A_BOLD)
        row += 1
        rows: List[List[str]] = []
        for client in sorted(clients.keys()):
            entry = clients[client] or {}
            rows.append(
                [
                    str(client),
                    str(entry.get("total", 0)),
                    str(entry.get("allowed", 0)),
                    str(entry.get("blocked", 0)),
                ]
            )
        render_table(
            window,
            row,
            left,
            width,
            ["client", "total", "allowed", "blocked"],
            rows,
            weights=[3, 1, 1, 1],
            max_rows=max(1, top + height - row - 2),
        )

"""The Toney curses application.

The user interface never touches the service directly: every piece of
information comes from the control socket and every action is a protocol
command.  Socket errors are reported in the status line and never take the
application down.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from toney.client import ControlClient, ToneyError
from toney.supervisor import ServiceSupervisor
from toney.term import CURSES_AVAILABLE, curses
from toney.views import VIEWS
from toney.widgets import Rect, safe_addstr

HELP_LINES = [
    ("q", "quit the application"),
    ("?", "toggle this help overlay"),
    ("Tab / Shift-Tab", "switch between the views"),
    ("1 2 3 4 5", "jump to dashboard, logs, rules, service and router"),
    ("s", "start the service"),
    ("S", "stop the service"),
    ("r", "restart the service"),
    ("R", "reload the rule set"),
    ("g", "refresh the current view"),
    ("c", "edit the service configuration"),
    ("/", "search or filter the logs and the rules"),
    ("F", "filter the logs by client address"),
    ("arrows", "scroll the logs, pick actions"),
    ("a k d", "in the rules view: block a domain, keep a domain, delete the selected rule"),
    ("d b", "in the router view: deploy the rule set, roll back to the previous file"),
]


class HelpOverlay:
    """A modal overlay that lists the key bindings."""

    def __init__(self) -> None:
        self.closed = False

    def render(self, window) -> None:
        maxy, maxx = window.getmaxyx()
        width = min(maxx - 4, 52)
        height = min(maxy - 2, len(HELP_LINES) + 4)
        top = max(0, (maxy - height) // 2)
        left = max(0, (maxx - width) // 2)
        for index in range(height):
            safe_addstr(window, top + index, left, " " * (width - 2), curses.A_NORMAL)
        safe_addstr(window, top, left, "+" + "-" * (width - 2) + "+", curses.A_BOLD)
        safe_addstr(window, top + height - 1, left, "+" + "-" * (width - 2) + "+", curses.A_BOLD)
        for offset in range(1, height - 1):
            safe_addstr(window, top + offset, left, "|")
            safe_addstr(window, top + offset, left + width - 1, "|")
        safe_addstr(window, top + 1, left + 2, "Toney key bindings", curses.A_BOLD)
        row = top + 2
        for key, description in HELP_LINES:
            if row >= top + height - 2:
                break
            safe_addstr(window, row, left + 2, key.ljust(16), curses.A_BOLD)
            safe_addstr(window, row, left + 18, description[: width - 20])
            row += 1

    def handle_key(self, key: int) -> bool:
        self.closed = True
        return True


class ToneyApp:
    """The curses application."""

    TICK_MS = 500
    REFRESH_SECONDS = 5.0

    def __init__(
        self,
        config: Dict[str, Any],
        client_factory=None,
        supervisor=None,
    ) -> None:
        self.config = config or {}
        self.socket_path = os.path.expanduser(self.config.get("control_socket") or "")
        self._client_factory = client_factory or (lambda: ControlClient(self.socket_path))
        self.supervisor = supervisor if supervisor is not None else ServiceSupervisor(self.config)
        self.views = [factory(self) for factory in VIEWS]
        self.current = 0
        self.status_message = ""
        self.status_kind = "info"
        self.running = True
        self.overlay = None
        self.stdscr = None
        self._client = None
        self._reachable = False
        self._last_refresh = 0.0

    @property
    def current_view(self):
        return self.views[self.current]

    def client(self) -> ControlClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def reset_client(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def request(self, cmd: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a protocol request and turn failures into a status message."""
        try:
            data = self.client().request(cmd, params or {})
        except ToneyError as exc:
            self._reachable = False
            self.reset_client()
            self.set_status("{0}".format(exc), "error")
            return None
        self._reachable = True
        return data

    def set_status(self, message: str, kind: str = "info") -> None:
        self.status_message = message
        self.status_kind = kind

    def service_state(self) -> str:
        if self._reachable:
            return "running"
        if self.supervisor is not None and self.supervisor.pid:
            return "starting"
        return "stopped"

    def service_command(self) -> str:
        service = self.config.get("service") or {}
        return " ".join(str(part) for part in (service.get("command") or []))

    def prompt(self, label: str, initial: str = "") -> Optional[str]:
        if self.stdscr is None:
            return None
        from toney.widgets import prompt_text

        return prompt_text(self.stdscr, label, initial)

    def refresh_view(self, view=None, force: bool = False) -> None:
        target = view or self.current_view
        try:
            target.refresh()
        except ToneyError as exc:
            self.set_status("{0}".format(exc), "error")
        except Exception as exc:  # pragma: no cover - defensive
            self.set_status("refresh failed: {0}".format(exc), "error")
        self._last_refresh = time.monotonic()

    def switch_view(self, index: int) -> None:
        if not self.views:
            return
        self.current = index % len(self.views)
        self.refresh_view()

    def next_view(self, delta: int) -> None:
        self.switch_view(self.current + delta)

    def start_service(self) -> None:
        try:
            pid = self.supervisor.start()
        except ToneyError as exc:
            self.set_status("could not start the service: {0}".format(exc), "error")
            return
        self.set_status("service started (pid {0})".format(pid))
        self.reset_client()
        self.refresh_view()

    def stop_service(self) -> None:
        try:
            stopped = self.supervisor.stop()
        except ToneyError as exc:
            self.set_status("could not stop the service: {0}".format(exc), "error")
            return
        self.reset_client()
        self._reachable = False
        self.set_status("service stopped" if stopped else "stop requested")

    def restart_service(self) -> None:
        try:
            pid = self.supervisor.restart()
        except ToneyError as exc:
            self.set_status("could not restart the service: {0}".format(exc), "error")
            return
        self.reset_client()
        self.set_status("service restarted (pid {0})".format(pid))
        self.refresh_view()

    def reload_rules(self) -> None:
        data = self.request("rules.reload")
        if data is None:
            return
        self.set_status("rules reloaded: {0} rule(s)".format(data.get("count", 0)))
        self.refresh_view()

    def run_action(self, index: int) -> None:
        actions = (
            self.start_service,
            self.stop_service,
            self.restart_service,
            self.reload_rules,
        )
        if 0 <= index < len(actions):
            actions[index]()

    def open_config_editor(self) -> None:
        from toney.views.config_editor import ConfigEditor

        data = self.request("config.get")
        if data is None:
            return
        self.overlay = ConfigEditor(self, data)

    def handle_key(self, key: int) -> None:
        if key == -1:
            return
        if self.overlay is not None:
            if self.overlay.handle_key(key):
                self.overlay = None
            return
        if key == ord("q"):
            self.running = False
        elif key == ord("?"):
            self.overlay = HelpOverlay()
        elif key == ord("\t"):
            self.next_view(1)
        elif key == curses.KEY_BTAB:
            self.next_view(-1)
        elif ord("1") <= key <= ord("9"):
            self.switch_view(key - ord("1"))
        elif key == ord("s"):
            self.start_service()
        elif key == ord("S"):
            self.stop_service()
        elif key == ord("r"):
            self.restart_service()
        elif key == ord("R"):
            self.reload_rules()
        elif key == ord("g"):
            self.refresh_view()
        elif key == ord("c"):
            self.open_config_editor()
        else:
            try:
                self.current_view.handle_key(key)
            except Exception as exc:  # pragma: no cover - defensive
                self.set_status("key handling failed: {0}".format(exc), "error")

    def draw(self, window) -> None:
        try:
            window.erase()
        except Exception:
            pass
        maxy, maxx = window.getmaxyx()
        tabs = "   ".join(
            "{0}:{1}".format(index + 1, view.title) for index, view in enumerate(self.views)
        )
        header = " Toney  {0}".format(tabs)
        safe_addstr(window, 0, 0, header, curses.A_BOLD)
        state = "service: {0}".format(self.service_state())
        if len(header) + len(state) + 2 < maxx:
            attr = curses.A_BOLD if self.service_state() != "running" else curses.A_NORMAL
            safe_addstr(window, 0, maxx - len(state) - 1, state, attr)
        safe_addstr(window, 1, 0, "-" * max(0, maxx - 1), curses.A_DIM)
        body_top = 2
        body_height = max(1, maxy - 4)
        rect: Rect = (body_top, 0, body_height, maxx)
        try:
            self.current_view.render(window, rect)
        except Exception as exc:  # pragma: no cover - defensive
            safe_addstr(window, body_top, 0, "view error: {0}".format(exc))
        if self.overlay is not None:
            try:
                self.overlay.render(window)
            except Exception as exc:  # pragma: no cover - defensive
                safe_addstr(window, body_top, 0, "overlay error: {0}".format(exc))
        self.draw_status(window, maxy, maxx)

    def draw_status(self, window, maxy: int, maxx: int) -> None:
        message = self.status_message
        if not message:
            state = self.service_state()
            if state == "stopped":
                message = "the service is not running, press 's' to start it"
            elif state == "starting":
                message = "the service is starting, press 'g' to refresh"
            else:
                message = "connected to {0}".format(self.socket_path)
        attr = curses.A_BOLD if self.status_kind == "error" else curses.A_NORMAL
        safe_addstr(window, maxy - 2, 0, message[: maxx - 1], attr)
        footer = (
            "q quit  ? help  Tab view  s start  S stop  r restart  R reload  "
            "g refresh  c config"
        )
        safe_addstr(window, maxy - 1, 0, footer[: maxx - 1], curses.A_DIM)

    def run(self, window) -> int:
        self.stdscr = window
        try:
            curses.curs_set(0)
        except Exception:
            pass
        try:
            window.keypad(True)
            curses.noecho()
            curses.cbreak()
            window.timeout(self.TICK_MS)
        except Exception:
            pass
        self.refresh_view()
        while self.running:
            try:
                self.draw(window)
                key = window.getch()
                self.handle_key(key)
            except KeyboardInterrupt:
                break
            except Exception:
                continue
            if time.monotonic() - self._last_refresh >= self.REFRESH_SECONDS:
                self.refresh_view()
        self.cleanup()
        return 0

    def cleanup(self) -> None:
        self.reset_client()
        try:
            if self.supervisor is not None and self.config.get("stop_on_exit", True):
                self.supervisor.cleanup()
        except Exception:
            pass


def run_app(config: Dict[str, Any]) -> int:
    """Start the curses application and return the exit code."""
    if not CURSES_AVAILABLE:
        raise RuntimeError(
            "the curses module is not available in this Python installation"
        )
    app = ToneyApp(config)
    return curses.wrapper(app.run)

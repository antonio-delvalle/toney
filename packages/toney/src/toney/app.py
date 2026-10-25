"""The Toney Textual application.

The interface is a Textual app: a header with the view tabs, the view
itself and a status line at the bottom.  Everything that talks to the
service lives in :mod:`toney.controller`, so the application only has to
turn protocol replies into widgets.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, ContentSwitcher, Static

from toney.controller import ToneyController
from toney.theme import THEMES
from toney.views import VIEWS, VIEW_NAMES
from toney.views.config_editor import ConfigEditorScreen
from toney.views.help import HelpScreen
from toney.views.prompt import PromptScreen

REFRESH_SECONDS = 5.0

HINT = (
    "q quit   ? help   Tab view   1-5 jump   s start   S stop   r restart   "
    "R reload   g refresh   c config"
)


class ToneyHeader(Horizontal):
    """The bar at the top: the title, the view tabs and the service state."""

    def compose(self) -> ComposeResult:
        yield Static("Toney", id="title")
        with Horizontal(id="tabs"):
            for view in VIEWS:
                yield Button(
                    view.title,
                    id="tab-{0}".format(view.name),
                    classes="tab",
                    flat=True,
                )
        yield Static("", id="service-state")


class StatusBar(Vertical):
    """The line at the bottom that carries the status message and the hints."""

    def compose(self) -> ComposeResult:
        yield Static("", id="status-message")
        yield Static("", id="status-hint")

    def set_message(self, message: str, kind: str) -> None:
        widget = self.query_one("#status-message", Static)
        widget.update(message)
        widget.set_class(kind == "error", "-error")

    def set_hint(self, hint: str) -> None:
        self.query_one("#status-hint", Static).update(hint)


class ToneyScreen(Screen):
    """The main screen: the header, the views and the status line."""

    BINDINGS = [
        Binding("tab", "app.next_view", "Next view"),
        Binding("shift+tab", "app.previous_view", "Previous view"),
    ]

    def compose(self) -> ComposeResult:
        yield ToneyHeader(id="header")
        with ContentSwitcher(id="views", initial=VIEW_NAMES[0]):
            for view in VIEWS:
                yield view()
        yield StatusBar(id="status-bar")


class ToneyApp(App):
    """The Toney terminal interface."""

    CSS_PATH = "toney.tcss"
    TITLE = "Toney"
    SUB_TITLE = "dnsguard"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("1", "view(0)", "Dashboard"),
        Binding("2", "view(1)", "Logs"),
        Binding("3", "view(2)", "Rules"),
        Binding("4", "view(3)", "Service"),
        Binding("5", "view(4)", "Router"),
        Binding("s", "start_service", "Start"),
        Binding("S", "stop_service", "Stop"),
        Binding("r", "restart_service", "Restart"),
        Binding("R", "reload_rules", "Reload"),
        Binding("g", "refresh", "Refresh"),
        Binding("c", "config", "Config"),
        Binding("/", "search", "Search"),
        Binding("a", "view_key('a')", "Block domain"),
        Binding("k", "view_key('k')", "Keep domain"),
        Binding("d", "view_key('d')", "Delete rule / device names"),
        Binding("b", "view_key('b')", "Roll back"),
    ]

    status_message = reactive("")
    status_kind = reactive("info")
    service_state = reactive("stopped")

    def __init__(
        self,
        config: Dict[str, Any],
        client_factory=None,
        supervisor=None,
    ) -> None:
        super().__init__()
        self.config = config or {}
        self.controller = ToneyController(
            self.config,
            client_factory=client_factory,
            supervisor=supervisor,
            on_status=self._on_status,
        )
        self.view_index = 0
        self._cleaned = False
        self._sweeping = False
        self._sweep_report = False
        self.main_screen: Optional[ToneyScreen] = None
        for theme in THEMES:
            self.register_theme(theme)
        self.theme = THEMES[0].name

    def get_default_screen(self) -> Screen:
        screen = ToneyScreen()
        self.main_screen = screen
        return screen

    def on_mount(self) -> None:
        self.set_interval(REFRESH_SECONDS, self.refresh_view)
        self.call_after_refresh(self.refresh_view)
        self.call_after_refresh(self._startup_sweep)

    def _startup_sweep(self) -> None:
        """Find the device names once, if the service is there to ask."""
        if self.controller.reachable:
            self._sweep_devices()

    def on_unmount(self) -> None:
        self._cleanup()

    async def action_quit(self) -> None:
        self._cleanup()
        self.exit()

    def _cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        self.controller.cleanup()

    @property
    def current_view(self):
        """The view that is on screen."""
        switcher = self.switcher
        if switcher is None:
            return None
        return switcher.children[self.view_index]

    @property
    def switcher(self):
        """The content switcher that holds the views."""
        if self.main_screen is None:
            return None
        return self.main_screen.query_one("#views", ContentSwitcher)

    def _on_status(self, message: str, kind: str) -> None:
        self.status_message = message
        self.status_kind = kind
        self.service_state = self.controller.service_state()

    def watch_status_message(self, value: str) -> None:
        self._sync_status()

    def watch_status_kind(self, value: str) -> None:
        self._sync_status()

    def watch_service_state(self, value: str) -> None:
        self._sync_status()

    def watch_theme(self, theme: str) -> None:
        """Draw the view again, so the text it built follows the new theme."""
        self.refresh_view()

    def default_status(self) -> str:
        """The message shown when nothing else has been said yet."""
        if self.service_state == "stopped":
            return "the service is not running, press 's' to start it"
        if self.service_state == "starting":
            return "the service is starting, press 'g' to refresh"
        return "connected to {0}".format(self.controller.socket_path)

    def _sync_status(self) -> None:
        if not self.is_mounted or self.main_screen is None:
            return
        try:
            bar = self.main_screen.query_one(StatusBar)
        except Exception:
            return
        bar.set_message(self.status_message or self.default_status(), self.status_kind)
        bar.set_hint(HINT)
        try:
            state = self.main_screen.query_one("#service-state", Static)
        except Exception:
            return
        state.update("service: {0}".format(self.service_state))
        state.set_class(self.service_state != "running", "-not-running")

    def _sync_tabs(self) -> None:
        if self.main_screen is None:
            return
        try:
            tabs = self.main_screen.query_one("#tabs")
        except Exception:
            return
        for index, view in enumerate(VIEWS):
            try:
                button = tabs.query_one("#tab-{0}".format(view.name), Button)
            except Exception:
                continue
            button.set_class(index == self.view_index, "-active")

    def show_view(self, index: int) -> None:
        """Show the view at *index* and load its data."""
        if not VIEWS:
            return
        self.view_index = index % len(VIEWS)
        switcher = self.switcher
        if switcher is None:
            return
        switcher.current = VIEW_NAMES[self.view_index]
        self._sync_tabs()
        self.refresh_view()

    def refresh_view(self, view=None) -> None:
        """Reload the data of the view that is on screen."""
        target = view or self.current_view
        if target is None:
            return
        try:
            target.load_data()
        except Exception as exc:  # pragma: no cover - defensive
            self.controller.set_status("refresh failed: {0}".format(exc), "error")
        self.service_state = self.controller.service_state()
        self._sync_status()

    def action_view(self, index: int) -> None:
        self.show_view(index)

    def action_next_view(self) -> None:
        self.show_view(self.view_index + 1)

    def action_previous_view(self) -> None:
        self.show_view(self.view_index - 1)

    def action_refresh(self) -> None:
        self.refresh_view()

    def action_start_service(self) -> None:
        self.controller.start_service()
        self.refresh_view()
        self._sweep_devices()

    def action_stop_service(self) -> None:
        self.controller.stop_service()
        self.refresh_view()

    def action_restart_service(self) -> None:
        self.controller.restart_service()
        self.refresh_view()
        self._sweep_devices()

    def action_reload_rules(self) -> None:
        self.controller.reload_rules()
        self.refresh_view()
        self._sweep_devices()

    def action_sweep_devices(self) -> None:
        """Look for the names of the devices behind the addresses in the log.

        The lookups take their time, so they run in the background and the
        screen is drawn again when they are done.
        """
        self._sweep_devices(report=True)

    def _sweep_devices(self, report: bool = False) -> None:
        """Sweep the log for the device names.

        A sweep that was asked for says what it found; one that was part of
        the service lifecycle says nothing, so it does not push the status
        line around.
        """
        if self._sweeping:
            if report:
                self.controller.set_status("a sweep is already running")
            return
        self._sweeping = True
        self._sweep_report = report
        self.run_worker(self._sweep_worker, thread=True, group="devices")

    def _sweep_worker(self) -> None:
        try:
            found = self.controller.sweep_devices()
        except Exception:
            found = {}
        self.call_from_thread(self._sweep_done, found)

    def _sweep_done(self, found: Dict[str, str]) -> None:
        self._sweeping = False
        self.refresh_view()
        if not self._sweep_report:
            return
        known = len(self.controller.device_names())
        if found:
            self.controller.set_status(
                "found {0} device name(s)".format(len(found))
            )
        elif known:
            self.controller.set_status(
                "the names of {0} device(s) are known".format(known)
            )
        else:
            self.controller.set_status("no device names found in the log")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_config(self) -> None:
        data = self.controller.request("config.get")
        if data is None:
            return
        self.push_screen(ConfigEditorScreen(data))

    def action_search(self) -> None:
        """Focus the search box of the view that is on screen."""
        try:
            field = self.current_view.search_input()
        except Exception:
            field = None
        if field is not None:
            field.focus()

    def prompt_for(self, label: str, initial: str, callback) -> None:
        """Ask the user for a line of text and hand the answer to *callback*."""
        self.push_screen(PromptScreen(label, initial), callback)

    def action_view_key(self, char: str) -> None:
        """Hand a character to the view that is on screen."""
        try:
            view = self.current_view
        except Exception:
            return
        if view.handle_char(char):
            self.refresh_view(view)
            return
        if char == "d":
            self.action_sweep_devices()


def run_app(config: Dict[str, Any]) -> int:
    """Start the Toney interface and return the exit code."""
    app = ToneyApp(config)
    app.run()
    return app.return_code or 0

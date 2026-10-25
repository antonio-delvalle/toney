"""Service view: lifecycle actions for the dnsguard process."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from toney.formatting import format_duration
from toney.views.base import ToneyView, pairs_block


class ServiceView(ToneyView):
    """Shows the state of the service and the lifecycle actions."""

    name = "service"
    title = "Service"

    def compose(self) -> ComposeResult:
        with Horizontal(id="actions"):
            yield Button("Start", id="start", flat=True)
            yield Button("Stop", id="stop", flat=True)
            yield Button("Restart", id="restart", flat=True)
            yield Button("Reload rules", id="reload", flat=True)
        yield Static("", id="service-detail")

    def load_data(self) -> None:
        if not self.is_mounted:
            return
        data = self.controller.request("status")
        if data is None:
            data = {}
        else:
            self.data = data
        self.query_one("#service-detail", Static).update(
            pairs_block(
                [
                    ("state", self.controller.service_state()),
                    ("pid", data.get("pid", "-")),
                    ("uptime", format_duration(data.get("uptime_s"))),
                    ("socket", self.controller.socket_path),
                    ("command", self.controller.service_command() or "-"),
                    ("version", data.get("version", "-")),
                ],
                self.colors,
            )
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.controller.start_service()
        elif event.button.id == "stop":
            self.controller.stop_service()
        elif event.button.id == "restart":
            self.controller.restart_service()
        elif event.button.id == "reload":
            self.controller.reload_rules()
        else:
            return
        self.load_data()

"""Configuration editor overlay.

The editor changes the service configuration through the ``config.set``
command.  Only the documented keys are touched: ``listen``, ``upstream``,
``log_dir`` and ``retention_days``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

FIELDS = (
    ("listen", "address to bind the DNS socket to"),
    ("upstream", "comma separated list of upstream resolvers"),
    ("log_dir", "directory the query log is written to"),
    ("retention_days", "number of days the query log is kept"),
)


class ConfigEditorScreen(ModalScreen):
    """A small modal form for the runtime configuration of the service."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, values: Dict[str, Any]) -> None:
        super().__init__()
        self.values = values or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="config-box"):
            yield Static("Service configuration", classes="prompt-label")
            with Vertical(id="config-fields"):
                for name, hint in FIELDS:
                    yield Static(hint, classes="field-hint")
                    yield Input(value=self._value_for(name), id="field-{0}".format(name))
            with Horizontal(id="config-actions"):
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#field-listen", Input).focus()

    def _value_for(self, name: str) -> str:
        value = self.values.get(name)
        if name == "upstream":
            return ", ".join(str(part) for part in (value or []))
        return "" if value is None else str(value)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "apply":
            self.dismiss(self.apply())
        else:
            self.dismiss(False)

    def apply(self) -> bool:
        params: Dict[str, Any] = {}
        for name, _hint in FIELDS:
            value = self.query_one("#field-{0}".format(name), Input).value.strip()
            if not value:
                continue
            if name == "upstream":
                params["upstream"] = [part.strip() for part in value.split(",") if part.strip()]
            elif name == "retention_days":
                try:
                    params["retention_days"] = int(value)
                except ValueError:
                    self.app.controller.set_status(
                        "retention days must be a whole number", "error"
                    )
                    return False
            else:
                params[name] = value
        if not params:
            self.app.controller.set_status("nothing to apply", "error")
            return False
        result = self.app.controller.request("config.set", params)
        if result is None:
            return False
        self.app.controller.set_status("configuration applied")
        return True

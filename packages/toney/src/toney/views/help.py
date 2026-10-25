"""The help overlay: a list of the key bindings."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from toney.theme import palette

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
    ("a k d", "in the rules view: block a domain, keep a domain, delete the selected rule"),
    ("d b", "in the router view: deploy the rule set, roll back to the previous file"),
    ("ctrl+p", "open the command palette, where the theme can be changed"),
]


class HelpScreen(ModalScreen):
    """A modal that lists the key bindings."""

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        colors = palette(self.app.theme)
        text = Text()
        text.append("Toney key bindings\n\n", style="bold {0}".format(colors["text"]))
        for key, description in HELP_LINES:
            text.append("{0:<18}".format(key), style="bold {0}".format(colors["keep"]))
            text.append("{0}\n".format(description), style=colors["text"])
        with Vertical(id="help-box"):
            yield Static(text)
            yield Button("Close", id="close")

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(None)

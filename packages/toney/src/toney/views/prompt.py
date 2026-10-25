"""A small modal that asks for one line of text."""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class PromptScreen(ModalScreen):
    """Ask the user for a single line of text.

    The screen is dismissed with the text the user typed, or with ``None``
    when the prompt was cancelled.
    """

    BINDINGS = [("escape", "dismiss_prompt", "Cancel")]

    def __init__(self, prompt: str, initial: str = "") -> None:
        super().__init__()
        self.prompt = prompt
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box"):
            yield Static(self.prompt, classes="prompt-label")
            yield Input(value=self.initial, id="prompt-input")
            with Horizontal(id="prompt-actions"):
                yield Button("OK", id="prompt-ok", variant="primary")
                yield Button("Cancel", id="prompt-cancel")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def action_dismiss_prompt(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "prompt-ok":
            self.dismiss(self.query_one("#prompt-input", Input).value)
        else:
            self.dismiss(None)

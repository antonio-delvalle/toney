"""Router view: deploy the rule set to a router that runs dnsmasq."""

from __future__ import annotations

from typing import Any, Dict, List

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from toney.views.base import ToneyView, pairs_block


class RouterView(ToneyView):
    """Shows the state of the generated rule file on the router."""

    name = "router"
    title = "Router"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.state: Dict[str, Any] = {}
        self.history: List[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="actions"):
            yield Button("Deploy", id="deploy", flat=True)
            yield Button("Roll back", id="rollback", flat=True)
        yield Static("", id="router-detail")
        yield Static("", id="router-history", classes="section-title")

    def load_data(self) -> None:
        if not self.is_mounted:
            return
        data = self.controller.request("router.status")
        if data is None:
            return
        self.data = data
        self.state = dict(data)
        self._fill()

    def deploy(self) -> None:
        data = self.controller.request("router.deploy")
        if data is None:
            return
        self.history.insert(
            0,
            "deployed {0} rule(s), {1} skipped, {2} byte(s)".format(
                data.get("rules", 0), data.get("skipped", 0), data.get("bytes", 0)
            ),
        )
        self.controller.set_status("rule set deployed to the router")
        self.load_data()

    def rollback(self) -> None:
        data = self.controller.request("router.rollback")
        if data is None:
            return
        if data.get("removed"):
            message = "the generated file was removed from the router"
        else:
            message = "the previous file was restored"
        self.history.insert(0, message)
        self.controller.set_status(message)
        self.load_data()

    def _fill(self) -> None:
        state = self.state
        if not state.get("configured"):
            self.query_one("#router-detail", Static).update(
                "No router is configured.\n"
                'Add a "router" section to the dnsguard configuration to use this view.'
            )
            self.query_one("#router-history", Static).update("")
            return
        self.query_one("#router-detail", Static).update(
            pairs_block(
                [
                    ("router host", state.get("host")),
                    ("remote file", state.get("remote_path")),
                    ("installed", "yes" if state.get("installed") else "no"),
                    ("matches the rules", "yes" if state.get("matches") else "no"),
                    ("remote size", "{0} byte(s)".format(state.get("bytes", 0))),
                ],
                self.colors,
            )
        )
        self.query_one("#router-history", Static).update("\n".join(self.history))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "deploy":
            self.deploy()
        elif event.button.id == "rollback":
            self.rollback()

    def handle_char(self, char: str) -> bool:
        if char == "d":
            self.deploy()
            return True
        if char == "b":
            self.rollback()
            return True
        return False

"""Rules view: the active rule set, with editing."""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Static

from toney.views.base import ToneyView


class RulesView(ToneyView):
    """Lists the rules known to the service with a search box, and edits them."""

    name = "rules"
    title = "Rules"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.search = ""
        self.rules: List[dict] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="filters"):
            yield Input(placeholder="search rules", id="search")
            yield Button("Block", id="add-block", flat=True)
            yield Button("Keep", id="add-allow", flat=True)
            yield Button("Delete", id="delete", flat=True)
        yield Static("", id="rule-summary", classes="section-title")
        yield DataTable(id="rules")

    def on_mount(self) -> None:
        table = self.query_one("#rules", DataTable)
        table.add_columns("pattern", "action", "source", "line")
        table.cursor_type = "row"

    def search_input(self) -> Optional[Input]:
        return self.query_one("#search", Input)

    def load_data(self) -> None:
        if not self.is_mounted:
            return
        data = self.controller.request("rules.list")
        if data is None:
            return
        self.data = data
        self.rules = list(data.get("rules") or [])
        self._fill_rules()

    def matching_rules(self) -> List[dict]:
        """The rules the current search shows, in the order they are shown."""
        if not self.search:
            return list(self.rules)
        needle = self.search.lower()
        return [
            rule
            for rule in self.rules
            if needle in str(rule.get("pattern", "")).lower()
            or needle in str(rule.get("source", "")).lower()
            or needle in str(rule.get("action", "")).lower()
        ]

    def selected_rule(self) -> Tuple[Optional[dict], int]:
        """The highlighted rule and its position in the full rule list."""
        shown = self.matching_rules()
        if not shown:
            return None, -1
        table = self.query_one("#rules", DataTable)
        index = min(table.cursor_row, len(shown) - 1)
        if index < 0:
            return None, -1
        rule = shown[index]
        position = next((p for p, r in enumerate(self.rules) if r is rule), -1)
        return rule, position

    def rules_path(self) -> str:
        configured = self.app.config.get("rules_file")
        if not configured:
            configured = os.path.join(
                os.path.expanduser("~"), ".config", "toney", "rules.blocklist"
            )
        return os.path.abspath(os.path.expanduser(configured))

    def rule_text(self, rules) -> str:
        lines = ["# edited by toney"]
        for rule in rules:
            pattern = str(rule.get("pattern", "")).strip()
            if not pattern:
                continue
            if str(rule.get("action")) == "allow" and not pattern.startswith("@@"):
                pattern = "@@" + pattern
            lines.append(pattern)
        return "\n".join(lines) + "\n"

    def apply_rules(self, rules) -> bool:
        path = self.rules_path()
        try:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.rule_text(rules))
        except OSError as exc:
            self.controller.set_status("could not write {0}: {1}".format(path, exc), "error")
            return False
        data = self.controller.request("rules.set", {"path": path})
        if data is None:
            return False
        self.controller.set_status(
            "rules applied: {0} rule(s) in {1}".format(data.get("count", 0), path)
        )
        self.load_data()
        return True

    def add_rule(self, action: str) -> None:
        """Ask for a domain and add it to the rule set."""
        label = "Block domain: " if action == "block" else "Keep domain: "
        self.app.prompt_for(label, "", lambda value: self._add_rule(action, value))

    def _add_rule(self, action: str, value: Optional[str]) -> None:
        if value is None:
            return
        domain = value.strip().lower().strip(".")
        if not domain or " " in domain:
            self.controller.set_status("that is not a domain name", "error")
            return
        pattern = "||{0}^".format(domain)
        updated = list(self.rules)
        updated.append({"pattern": pattern, "action": action, "source": "toney", "line": 0})
        self.apply_rules(updated)

    def delete_selected(self) -> None:
        rule, position = self.selected_rule()
        if rule is None or position < 0:
            self.controller.set_status("there is no rule to delete", "error")
            return
        updated = [r for index, r in enumerate(self.rules) if index != position]
        if not self.apply_rules(updated):
            return
        self.controller.set_status("deleted {0}".format(rule.get("pattern", "")))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.search = event.value.strip()
        self.load_data()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.search = event.value.strip()
        self._fill_rules()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-block":
            self.add_rule("block")
        elif event.button.id == "add-allow":
            self.add_rule("allow")
        elif event.button.id == "delete":
            self.delete_selected()

    def _fill_rules(self) -> None:
        table = self.query_one("#rules", DataTable)
        table.clear()
        shown = self.matching_rules()
        for rule in shown:
            table.add_row(
                str(rule.get("pattern", "")),
                str(rule.get("action", "")),
                str(rule.get("source", "")),
                str(rule.get("line", "")),
            )
        self.query_one("#rule-summary", Static).update(
            "search: {0}    showing {1} of {2} rules".format(
                self.search or "(none)", len(shown), len(self.rules)
            )
        )

    def handle_char(self, char: str) -> bool:
        if char == "a":
            self.add_rule("block")
            return True
        if char == "k":
            self.add_rule("allow")
            return True
        if char == "d":
            self.delete_selected()
            return True
        return False

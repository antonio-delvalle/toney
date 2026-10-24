"""Rules view: the active rule set, with editing."""

from __future__ import annotations

import os
from typing import List

from toney.term import curses
from toney.views.base import View
from toney.widgets import Rect, render_table, safe_addstr


class RulesView(View):
    """Lists the rules known to the service with a search box, and edits them."""

    name = "rules"
    title = "Rules"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.search = ""
        self.rules: List[dict] = []
        self.selected = 0

    def refresh(self) -> None:
        data = self.app.request("rules.list")
        if data is not None:
            self.data = data
            self.rules = list(data.get("rules") or [])
            self.selected = min(self.selected, max(0, len(self.rules) - 1))

    def matching_rules(self) -> List[dict]:
        if not self.search:
            return self.rules
        needle = self.search.lower()
        return [
            rule
            for rule in self.rules
            if needle in str(rule.get("pattern", "")).lower()
            or needle in str(rule.get("source", "")).lower()
            or needle in str(rule.get("action", "")).lower()
        ]

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
            self.app.set_status("could not write {0}: {1}".format(path, exc), "error")
            return False
        data = self.app.request("rules.set", {"path": path})
        if data is None:
            return False
        self.app.set_status(
            "rules applied: {0} rule(s) in {1}".format(data.get("count", 0), path)
        )
        self.refresh()
        return True

    def add_rule(self, action: str) -> bool:
        label = "Block domain: " if action == "block" else "Keep domain: "
        value = self.app.prompt(label, "")
        if value is None:
            return False
        domain = value.strip().lower().strip(".")
        if not domain or " " in domain:
            self.app.set_status("that is not a domain name", "error")
            return False
        pattern = "||{0}^".format(domain)
        updated = list(self.rules)
        updated.append({"pattern": pattern, "action": action, "source": "toney", "line": 0})
        return self.apply_rules(updated)

    def delete_selected(self) -> bool:
        if not self.rules:
            self.app.set_status("there is no rule to delete", "error")
            return False
        index = min(self.selected, len(self.rules) - 1)
        rule = self.rules[index]
        updated = [r for position, r in enumerate(self.rules) if position != index]
        if not self.apply_rules(updated):
            return False
        self.selected = max(0, index - 1)
        self.app.set_status("deleted {0}".format(rule.get("pattern", "")))
        return True

    def render(self, window, rect: Rect) -> None:
        top, left, height, width = rect
        total = len(self.rules)
        shown = len(self.matching_rules())
        safe_addstr(
            window,
            top,
            left,
            "search: {0}    showing {1} of {2} rules    [a] block  [k] keep  [d] delete".format(
                self.search or "(none)", shown, total
            ),
            curses.A_DIM,
        )
        row = top + 1
        rules = self.matching_rules()
        if not rules:
            safe_addstr(window, row, left, "No rules match the current search.")
            return
        rows = []
        for rule in rules:
            rows.append(
                [
                    str(rule.get("pattern", "")),
                    str(rule.get("action", "")),
                    str(rule.get("source", "")),
                    str(rule.get("line", "")),
                ]
            )
        render_table(
            window,
            row,
            left,
            width,
            ["pattern", "action", "source", "line"],
            rows,
            weights=[4, 1, 2, 1],
            max_rows=max(1, top + height - row - 1),
            selected=self.selected if self.selected < len(rules) else None,
        )

    def handle_key(self, key: int) -> bool:
        if key == ord("/"):
            value = self.app.prompt("Rule search: ", self.search)
            if value is not None:
                self.search = value.strip()
                self.selected = 0
            return True
        if key == ord("a"):
            self.add_rule("block")
            return True
        if key == ord("k"):
            self.add_rule("allow")
            return True
        if key == ord("d"):
            self.delete_selected()
            return True
        if key == curses.KEY_UP:
            self.selected = max(0, self.selected - 1)
            return True
        if key == curses.KEY_DOWN:
            self.selected = min(max(0, len(self.rules) - 1), self.selected + 1)
            return True
        return False

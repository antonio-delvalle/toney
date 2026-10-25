"""Base class for the views of the Toney interface."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Input

from toney.formatting import format_timestamp
from toney.theme import COLORS, decision_color, palette

LOG_COLUMNS = ("timestamp", "client", "name", "decision", "rule")

LABEL_WIDTH = 10
MIN_VALUE = 4


def _shorten(value: str, room: Optional[int]) -> str:
    """Cut a value down to the room it has."""
    if not room:
        return value
    if len(value) <= room:
        return value
    if room < 1:
        return ""
    if room == 1:
        return "…"
    return value[: room - 1] + "…"


def summary_card(
    title: str,
    rows: List[Tuple[str, str]],
    width: Optional[int] = None,
    colors: Optional[Dict[str, str]] = None,
) -> Text:
    """Build the body of a summary card: a title and a list of pairs.

    *width* is the number of columns the card has for its text.  Labels and
    values that do not fit are cut with an ellipsis, so a card keeps one line
    per row however narrow it gets.
    """
    colors = colors or COLORS
    longest = max((len(label) for label, _value in rows), default=0)
    if width:
        room = max(MIN_VALUE, width - (longest + 1))
        label_width = width - room
        if label_width > longest + 1:
            label_width = longest + 1
            room = width - label_width
    else:
        label_width = min(LABEL_WIDTH, longest + 1)
        room = None
    text = Text()
    text.append("{0}\n".format(title), style="bold {0}".format(colors["text"]))
    for label, value in rows:
        text.append(
            "{0:<{1}}".format(_shorten(label, label_width), label_width),
            style=colors["dim"],
        )
        text.append(
            "{0}\n".format(_shorten(str(value), room)), style=colors["text"]
        )
    return text


def pairs_block(
    rows: List[Tuple[str, str]], colors: Optional[Dict[str, str]] = None
) -> Text:
    """Build a block of label and value pairs without a title."""
    colors = colors or COLORS
    text = Text()
    for label, value in rows:
        text.append("{0:<18}".format(label), style=colors["dim"])
        text.append("{0}\n".format(value), style=colors["text"])
    return text


def device_cell(name: str, colors: Optional[Dict[str, str]] = None) -> Text:
    """Build the device name of a client."""
    colors = colors or COLORS
    if not name:
        return Text("-", style=colors["dim"])
    return Text(name, style="bold {0}".format(colors["accent"]))


def client_cell(
    client: str, names: Dict[str, str], colors: Optional[Dict[str, str]] = None
) -> Text:
    """Build the client cell: the device name first, then the address."""
    colors = colors or COLORS
    address = str(client or "")
    name = str(names.get(address, "") or "")
    if not name:
        return Text(address, style=colors["text"])
    text = Text(name, style="bold {0}".format(colors["accent"]))
    text.append("  ")
    text.append(address, style=colors["text"])
    return text


def decision_cell(
    decision: str, colors: Optional[Dict[str, str]] = None
) -> Text:
    """Build the decision cell, coloured by what the decision means."""
    return Text(
        str(decision or ""), style=decision_color(decision, colors or COLORS)
    )


def log_row(
    record: Dict[str, Any],
    names: Dict[str, str],
    colors: Optional[Dict[str, str]] = None,
) -> List[Text]:
    """Build the cells of a log record."""
    colors = colors or COLORS
    return [
        Text(format_timestamp(record.get("ts"))),
        client_cell(str(record.get("client", "")), names, colors),
        Text(str(record.get("name", ""))),
        decision_cell(str(record.get("decision", "")), colors),
        Text(str(record.get("rule", "") or "")),
    ]


class ToneyView(Vertical):
    """A single view of the Toney interface."""

    name = "view"
    title = "View"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("id", self.name)
        super().__init__(**kwargs)
        self.data: Optional[Dict[str, Any]] = None

    @property
    def controller(self):
        """The controller the view reads its data from."""
        return self.app.controller

    @property
    def colors(self) -> Dict[str, str]:
        """The colours of the theme that is on screen."""
        return palette(self.app.theme)

    def device_names(self) -> Dict[str, str]:
        """The address to device name mapping.

        The names that were found in the log, with the ones written in the
        configuration on top of them.
        """
        return self.controller.device_names()

    def load_data(self) -> None:
        """Reload whatever the view shows from the service."""

    def handle_char(self, char: str) -> bool:
        """Handle a character key press.  True when the key was consumed."""
        return False

    def search_input(self) -> Optional[Input]:
        """The input that the search shortcut focuses, if the view has one."""
        return None

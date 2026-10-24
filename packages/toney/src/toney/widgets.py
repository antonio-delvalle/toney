"""Small curses helpers shared by the Toney views."""

from __future__ import annotations

from toney.term import curses
from typing import List, Optional, Sequence, Tuple

Rect = Tuple[int, int, int, int]

TICK_MS = 500


def safe_addstr(window, y: int, x: int, text: str, attr: int = 0) -> None:
    """Print *text* at the given position, clipping instead of raising."""
    if not text:
        return
    try:
        maxy, maxx = window.getmaxyx()
    except curses.error:
        return
    if y < 0 or y >= maxy:
        return
    if x < 0:
        text = text[-x:]
        x = 0
        if not text:
            return
    if x >= maxx:
        return
    text = text[: maxx - x - 1]
    if not text:
        return
    try:
        window.addstr(y, x, text, attr)
    except curses.error:
        pass


def format_bytes(value) -> str:
    """Render a byte count in a human readable way."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(number) < 1024.0:
            if unit == "B":
                return "{0:.0f} {1}".format(number, unit)
            return "{0:.1f} {1}".format(number, unit)
        number /= 1024.0
    return "{0:.1f} PiB".format(number)


def format_duration(seconds) -> str:
    """Render a duration in seconds as a compact human readable string."""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "-"
    if total < 0:
        return "-"
    if total < 60:
        return "{0}s".format(total)
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return "{0}m {1}s".format(minutes, secs)
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return "{0}h {1}m".format(hours, minutes)
    days, hours = divmod(hours, 24)
    return "{0}d {1}h {2}m".format(days, hours, minutes)


def render_table(
    window,
    top: int,
    left: int,
    width: int,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    weights: Optional[Sequence[int]] = None,
    selected: Optional[int] = None,
    max_rows: Optional[int] = None,
) -> int:
    """Render a simple table and return the number of rows that were drawn."""
    if not headers:
        return 0
    column_count = len(headers)
    if not weights or len(weights) != column_count:
        weights = [1] * column_count
    total_weight = sum(weights) or 1
    usable = max(1, width - 1)
    widths = [max(3, int(usable * weight / total_weight)) for weight in weights]
    overflow = sum(widths) - usable
    while overflow > 0:
        widest = widths.index(max(widths))
        if widths[widest] <= 3:
            break
        widths[widest] -= 1
        overflow -= 1
    header = " ".join(
        str(head)[: widths[index]].ljust(widths[index]) for index, head in enumerate(headers)
    )
    safe_addstr(window, top, left, header, curses.A_BOLD)
    drawn = 0
    limit = max_rows if max_rows is not None else 10000
    for offset, row in enumerate(rows):
        if drawn >= limit:
            break
        cells = []
        for index in range(column_count):
            value = str(row[index]) if index < len(row) else ""
            cells.append(value[: widths[index]].ljust(widths[index]))
        attr = curses.A_REVERSE if selected is not None and selected == offset else 0
        safe_addstr(window, top + 1 + drawn, left, " ".join(cells), attr)
        drawn += 1
    return drawn


def prompt_text(window, prompt: str, initial: str = "") -> Optional[str]:
    """Ask for a single line of text.  Returns None when cancelled."""
    value = initial
    cursor = len(value)
    window.timeout(-1)
    try:
        return _prompt_loop(window, prompt, value, cursor)
    finally:
        window.timeout(TICK_MS)


def _prompt_loop(window, prompt: str, value: str, cursor: int) -> Optional[str]:
    while True:
        try:
            window.erase()
        except curses.error:
            pass
        maxy, maxx = window.getmaxyx()
        safe_addstr(window, maxy - 2, 0, prompt)
        safe_addstr(window, maxy - 1, 0, value)
        try:
            window.move(maxy - 1, min(cursor, maxx - 1))
        except curses.error:
            pass
        try:
            window.refresh()
        except curses.error:
            pass
        try:
            key = window.getch()
        except curses.error:
            return None
        if key in (curses.KEY_ENTER, 10, 13):
            return value
        if key == 27:
            return None
        if key in (curses.KEY_BACKSPACE, 127, 8):
            if cursor > 0:
                value = value[: cursor - 1] + value[cursor:]
                cursor -= 1
            continue
        if key == curses.KEY_LEFT:
            cursor = max(0, cursor - 1)
            continue
        if key == curses.KEY_RIGHT:
            cursor = min(len(value), cursor + 1)
            continue
        if key == curses.KEY_HOME:
            cursor = 0
            continue
        if key == curses.KEY_END:
            cursor = len(value)
            continue
        if key < 32 and key not in (9,):
            continue
        if 32 <= key < 127:
            value = value[:cursor] + chr(key) + value[cursor:]
            cursor += 1

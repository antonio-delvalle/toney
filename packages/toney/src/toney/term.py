"""Curses import that degrades gracefully when the module is unavailable.

Some Python installations ship without a working ``_curses`` extension.  The
protocol client and the supervisor must stay importable in that case, so the
user interface modules import curses through this module and check
``CURSES_AVAILABLE`` before drawing anything.
"""

from __future__ import annotations

from typing import Any

try:
    import curses

    CURSES_AVAILABLE = True
except Exception:  # pragma: no cover - depends on the local Python build

    class _CursesStub:
        """Stand-in so that module level attribute access keeps working."""

        error = OSError

        def __getattr__(self, name: str) -> Any:
            return 0

    curses = _CursesStub()  # type: ignore[assignment]
    CURSES_AVAILABLE = False


def require_curses() -> Any:
    """Return the curses module or raise a helpful error."""
    if not CURSES_AVAILABLE:
        raise RuntimeError(
            "the curses module is not available in this Python installation"
        )
    return curses

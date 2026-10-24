"""Base class for the Toney views."""

from __future__ import annotations

from typing import Any, Dict, Optional

from toney.widgets import Rect


class View:
    """A single screen of the Toney user interface."""

    name = "view"
    title = "View"

    def __init__(self, app: Any) -> None:
        self.app = app
        self.data: Optional[Dict[str, Any]] = None

    def refresh(self) -> None:
        """Reload whatever the view shows from the service."""

    def render(self, window, rect: Rect) -> None:
        """Draw the view inside *rect* = (top, left, height, width)."""

    def handle_key(self, key: int) -> bool:
        """Handle a key press.  Returns True when the key was consumed."""
        return False

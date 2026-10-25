"""The views of the Toney interface.

``VIEWS`` is the registry the application walks to build the header, the
content switcher and the number shortcuts.
"""

from __future__ import annotations

from toney.views.base import ToneyView
from toney.views.dashboard import DashboardView
from toney.views.logs import LogsView
from toney.views.rules import RulesView
from toney.views.router import RouterView
from toney.views.service import ServiceView

VIEWS = (
    DashboardView,
    LogsView,
    RulesView,
    ServiceView,
    RouterView,
)

VIEW_NAMES = tuple(view.name for view in VIEWS)

__all__ = [
    "ToneyView",
    "DashboardView",
    "LogsView",
    "RulesView",
    "RouterView",
    "ServiceView",
    "VIEWS",
    "VIEW_NAMES",
]

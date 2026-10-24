"""The Toney views."""

from __future__ import annotations

from toney.views.base import View
from toney.views.dashboard import DashboardView
from toney.views.logs import LogsView
from toney.views.router import RouterView
from toney.views.rules import RulesView
from toney.views.service import ServiceView

VIEWS = (DashboardView, LogsView, RulesView, ServiceView, RouterView)

__all__ = [
    "View",
    "VIEWS",
    "DashboardView",
    "LogsView",
    "RulesView",
    "ServiceView",
    "RouterView",
]

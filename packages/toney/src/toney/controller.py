"""Everything the interface needs that is not a pixel.

The controller owns the control socket client, the service supervisor and
the status message.  It contains no terminal code at all, so the Textual
interface and the test suite can both drive it.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

from toney.client import ControlClient, ToneyError
from toney.supervisor import ServiceSupervisor


class ToneyController:
    """Talks to the service and remembers the outcome of the last exchange."""

    def __init__(
        self,
        config: Dict[str, Any],
        client_factory: Optional[Callable[[], ControlClient]] = None,
        supervisor: Optional[ServiceSupervisor] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.config = config or {}
        self.socket_path = os.path.expanduser(self.config.get("control_socket") or "")
        self._client_factory = client_factory or (lambda: ControlClient(self.socket_path))
        self.supervisor = supervisor if supervisor is not None else ServiceSupervisor(self.config)
        self._on_status = on_status
        self.status_message = ""
        self.status_kind = "info"
        self.reachable = False
        self._client: Optional[ControlClient] = None

    def client(self) -> ControlClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def reset_client(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def request(self, cmd: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a protocol request and turn failures into a status message."""
        try:
            data = self.client().request(cmd, params or {})
        except ToneyError as exc:
            self.reachable = False
            self.reset_client()
            self.set_status("{0}".format(exc), "error")
            return None
        self.reachable = True
        return data

    def set_status(self, message: str, kind: str = "info") -> None:
        self.status_message = message
        self.status_kind = kind
        if self._on_status is not None:
            self._on_status(message, kind)

    def service_state(self) -> str:
        if self.reachable:
            return "running"
        if self.supervisor is not None and self.supervisor.pid:
            return "starting"
        return "stopped"

    def service_command(self) -> str:
        service = self.config.get("service") or {}
        return " ".join(str(part) for part in (service.get("command") or []))

    def start_service(self) -> None:
        try:
            pid = self.supervisor.start()
        except ToneyError as exc:
            self.set_status("could not start the service: {0}".format(exc), "error")
            return
        self.set_status("service started (pid {0})".format(pid))
        self.reset_client()

    def stop_service(self) -> None:
        try:
            stopped = self.supervisor.stop()
        except ToneyError as exc:
            self.set_status("could not stop the service: {0}".format(exc), "error")
            return
        self.reset_client()
        self.reachable = False
        self.set_status("service stopped" if stopped else "stop requested")

    def restart_service(self) -> None:
        try:
            pid = self.supervisor.restart()
        except ToneyError as exc:
            self.set_status("could not restart the service: {0}".format(exc), "error")
            return
        self.reset_client()
        self.set_status("service restarted (pid {0})".format(pid))

    def reload_rules(self) -> None:
        data = self.request("rules.reload")
        if data is None:
            return
        self.set_status("rules reloaded: {0} rule(s)".format(data.get("count", 0)))

    def cleanup(self) -> None:
        self.reset_client()
        try:
            if self.supervisor is not None and self.config.get("stop_on_exit", True):
                self.supervisor.cleanup()
        except Exception:
            pass

"""Client for the dnsguard Unix domain socket control protocol.

The transport is a Unix domain socket carrying newline delimited JSON
objects.  Requests are ``{"id", "cmd", "params"}`` and responses are either
``{"id", "ok": true, "data"}`` or ``{"id", "ok": false, "error"}``.

Only the commands documented in the control protocol are implemented here.
"""

from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Dict, List, Optional

MAX_LINE_BYTES = 1024 * 1024


class ToneyError(Exception):
    """Base class for every error raised by this package."""


class ServiceUnreachable(ToneyError):
    """The control socket is missing or refused the connection."""


class ProtocolError(ToneyError):
    """The service answered something that is not a valid protocol reply."""


class RequestTimeout(ProtocolError):
    """The service did not answer within the configured timeout."""


class CommandError(ToneyError):
    """The service answered with ``ok: false``."""

    def __init__(self, message: str, cmd: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.cmd = cmd


class CommandNotSupported(CommandError):
    """The running service does not implement the requested command."""


class ControlClient:
    """Synchronous client for the control protocol."""

    def __init__(
        self,
        socket_path: str,
        timeout: float = 5.0,
        connect_timeout: float = 2.0,
        retries: int = 1,
        retry_delay: float = 0.25,
    ) -> None:
        self.socket_path = os.path.expanduser(socket_path)
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.retries = max(0, int(retries))
        self.retry_delay = retry_delay
        self._sock: Optional[socket.socket] = None
        self._buffer = b""
        self._next_id = 1

    def __enter__(self) -> "ControlClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self) -> None:
        """Open the control socket, raising ``ServiceUnreachable`` on failure."""
        if self._sock is not None:
            return
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.connect_timeout)
            sock.connect(self.socket_path)
        except FileNotFoundError as exc:
            sock.close()
            raise ServiceUnreachable(
                "service not reachable: control socket not found: {0}".format(
                    self.socket_path
                )
            ) from exc
        except ConnectionRefusedError as exc:
            sock.close()
            raise ServiceUnreachable(
                "service not reachable: connection refused by {0}".format(self.socket_path)
            ) from exc
        except OSError as exc:
            sock.close()
            raise ServiceUnreachable(
                "service not reachable: {0}: {1}".format(self.socket_path, exc)
            ) from exc
        sock.settimeout(self.timeout)
        self._sock = sock
        self._buffer = b""

    def close(self) -> None:
        """Close the connection if one is open.  Safe to call repeatedly."""
        sock, self._sock = self._sock, None
        self._buffer = b""
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def request(self, cmd: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a request and return the ``data`` payload of the reply."""
        if not cmd:
            raise ProtocolError("a command name is required")
        attempts = self.retries + 1
        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                self.connect()
            except ServiceUnreachable as exc:
                last_error = exc
                self.close()
                if attempt < attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                break
            try:
                return self._exchange(cmd, params or {})
            except ServiceUnreachable as exc:
                last_error = exc
                self.close()
                if attempt < attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                raise
        if isinstance(last_error, ServiceUnreachable):
            raise last_error
        raise ServiceUnreachable(
            "service not reachable: {0}".format(self.socket_path)
        ) from last_error

    def _exchange(self, cmd: str, params: Dict[str, Any]) -> Any:
        request_id = self._next_id
        self._next_id += 1
        payload = {"id": request_id, "cmd": cmd, "params": params}
        line = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if len(line) + 1 > MAX_LINE_BYTES:
            raise ProtocolError("request line exceeds the 1 MiB limit")
        assert self._sock is not None
        try:
            self._sock.sendall(line + b"\n")
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise ServiceUnreachable(
                "service not reachable: connection lost: {0}".format(exc)
            ) from exc
        except OSError as exc:
            raise ServiceUnreachable(
                "service not reachable: socket write failed: {0}".format(exc)
            ) from exc
        reply = self._read_reply()
        return self._decode(reply, request_id, cmd)

    def _read_reply(self) -> bytes:
        assert self._sock is not None
        while b"\n" not in self._buffer:
            try:
                chunk = self._sock.recv(65536)
            except socket.timeout as exc:
                raise RequestTimeout(
                    "timed out waiting for a reply after {0:.1f}s".format(self.timeout)
                ) from exc
            except OSError as exc:
                raise ServiceUnreachable(
                    "service not reachable: socket read failed: {0}".format(exc)
                ) from exc
            if not chunk:
                raise ProtocolError("the service closed the connection")
            self._buffer += chunk
            if len(self._buffer) > MAX_LINE_BYTES:
                raise ProtocolError("reply line exceeds the 1 MiB limit")
        line, self._buffer = self._buffer.split(b"\n", 1)
        return line

    @staticmethod
    def _decode(reply: bytes, request_id: int, cmd: str) -> Any:
        try:
            decoded = json.loads(reply.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProtocolError("malformed reply: {0}".format(exc)) from exc
        if not isinstance(decoded, dict):
            raise ProtocolError("malformed reply: expected a JSON object")
        if "id" in decoded and decoded["id"] != request_id:
            raise ProtocolError(
                "reply id mismatch: expected {0}, got {1!r}".format(request_id, decoded["id"])
            )
        if "ok" not in decoded:
            raise ProtocolError("malformed reply: missing 'ok'")
        if decoded["ok"]:
            return decoded.get("data")
        message = decoded.get("error")
        if not isinstance(message, str):
            message = "the service reported an unspecified error"
        if message.startswith("unknown command"):
            raise CommandNotSupported(message, cmd)
        raise CommandError(message, cmd)

    def status(self) -> Dict[str, Any]:
        """Full service state."""
        return self.request("status") or {}

    def stats(self, window_s: int = 300) -> Dict[str, Any]:
        """Time bucketed counters plus the most frequent names."""
        return self.request("stats", {"window_s": int(window_s)}) or {}

    def rules_list(self) -> Dict[str, Any]:
        """The active rule set."""
        return self.request("rules.list") or {}

    def rules_reload(self) -> Dict[str, Any]:
        """Re-read every rule source file."""
        return self.request("rules.reload") or {}

    def rules_set(self, path: str) -> Dict[str, Any]:
        """Replace the active rule set with the contents of *path*."""
        return self.request("rules.set", {"path": os.path.expanduser(path)}) or {}

    def logs_tail(
        self,
        limit: int = 100,
        text_filter: Optional[str] = None,
        client: Optional[str] = None,
    ) -> Dict[str, Any]:
        """The most recent query log records, newest first."""
        params: Dict[str, Any] = {"limit": int(limit)}
        if text_filter:
            params["filter"] = text_filter
        if client:
            params["client"] = client
        return self.request("logs.tail", params) or {}

    def config_get(self) -> Dict[str, Any]:
        """The effective configuration of the service."""
        return self.request("config.get") or {}

    def config_set(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a partial configuration to the service."""
        return self.request("config.set", dict(changes or {})) or {}

    def upstream_set(
        self,
        servers: Optional[List[str]] = None,
        doh: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Swap the upstream resolver at runtime."""
        params: Dict[str, Any] = {}
        if servers is not None:
            params["servers"] = list(servers)
        if doh is not None:
            params["doh"] = doh
        return self.request("upstream.set", params) or {}

    def shutdown(self) -> Any:
        """Ask the service to stop gracefully."""
        return self.request("shutdown")

    def router_status(self) -> Dict[str, Any]:
        """Whether the rule set is installed on the configured router."""
        return self.request("router.status") or {}

    def router_deploy(self) -> Dict[str, Any]:
        """Write the rule set to the router and restart dnsmasq."""
        return self.request("router.deploy") or {}

    def router_rollback(self) -> Dict[str, Any]:
        """Restore the previous rule file on the router."""
        return self.request("router.rollback") or {}

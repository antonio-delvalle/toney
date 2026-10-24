"""Process supervision for the dnsguard service.

The supervisor starts the service as a detached child process, asks it to
stop over the control socket and falls back to signals when the service does
not cooperate.  Every method is safe to call repeatedly.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

from toney.client import ControlClient, ToneyError

DEFAULT_STATE_DIR = os.path.join("~", ".local", "state", "toney")


class ServiceSupervisor:
    """Start, stop and inspect the dnsguard service process."""

    def __init__(
        self,
        config: Dict[str, Any],
        client_factory: Optional[Callable[[], ControlClient]] = None,
        state_dir: Optional[str] = None,
    ) -> None:
        self.config = config or {}
        self.socket_path = os.path.expanduser(
            self.config.get("control_socket") or DEFAULT_STATE_DIR + "/dnsguard.sock"
        )
        self._client_factory = client_factory or (lambda: ControlClient(self.socket_path))
        self.state_dir = os.path.expanduser(state_dir or self._default_state_dir())
        self.pid_file = os.path.join(self.state_dir, "dnsguard.pid")
        self.log_file = os.path.join(self.state_dir, "dnsguard.out")
        self._child: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
        self._log_handle = None

    def _default_state_dir(self) -> str:
        directory = os.path.dirname(self.socket_path)
        return directory or DEFAULT_STATE_DIR

    @property
    def pid(self) -> Optional[int]:
        """The pid of the process this supervisor started, if any."""
        if self._child is not None and self._child.poll() is None:
            return self._child.pid
        if self._pid:
            return self._pid
        return self._read_pid_file()

    def _read_pid_file(self) -> Optional[int]:
        try:
            with open(self.pid_file, "r", encoding="utf-8") as handle:
                return int(handle.read().strip())
        except (OSError, ValueError):
            return None

    def _write_pid_file(self) -> None:
        if self._pid is None:
            return
        try:
            os.makedirs(self.state_dir, exist_ok=True)
            with open(self.pid_file, "w", encoding="utf-8") as handle:
                handle.write(str(self._pid))
        except OSError:
            pass

    def _remove_pid_file(self) -> None:
        try:
            os.unlink(self.pid_file)
        except OSError:
            pass

    @staticmethod
    def _pid_alive(pid: Optional[int]) -> bool:
        if not pid:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def _alive(self, pid: Optional[int]) -> bool:
        """Check whether *pid* is alive, reaping an owned child first."""
        if self._child is not None:
            self._child.poll()
        return self._pid_alive(pid)

    def _socket_present(self) -> bool:
        return os.path.exists(self.socket_path)

    def running(self) -> bool:
        """True when the service process is alive and answers on the socket."""
        if not self._alive(self.pid):
            return False
        try:
            client = self._client_factory()
            with client:
                client.status()
        except ToneyError:
            return False
        except OSError:
            return False
        return True

    def start(self) -> int:
        """Start the service and return its pid."""
        if self.running():
            return int(self.pid or 0)
        service = self.config.get("service") or {}
        command: List[str] = list(service.get("command") or [])
        if not command:
            raise ToneyError("no service command configured")
        cwd = service.get("cwd") or None
        env = os.environ.copy()
        for key, value in (service.get("env") or {}).items():
            env[str(key)] = str(value)
        self._close_log()
        try:
            os.makedirs(self.state_dir, exist_ok=True)
            self._log_handle = open(self.log_file, "ab", buffering=0)
        except OSError:
            self._log_handle = None
        try:
            self._child = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=self._log_handle if self._log_handle else subprocess.DEVNULL,
                stderr=subprocess.STDOUT if self._log_handle else subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            self._close_log()
            raise ToneyError("could not start the service: {0}".format(exc)) from exc
        self._pid = self._child.pid
        self._write_pid_file()
        return self._pid

    def stop(self, timeout: float = 10.0) -> bool:
        """Stop the service.  Returns True when the service is gone."""
        pid = self.pid
        graceful = False
        try:
            client = self._client_factory()
            with client:
                client.shutdown()
            graceful = True
        except ToneyError:
            graceful = False
        except OSError:
            graceful = False
        if graceful:
            deadline = time.monotonic() + max(0.0, timeout)
            while time.monotonic() < deadline:
                if not self._alive(pid):
                    self._reap()
                    self._remove_pid_file()
                    return True
                time.sleep(0.1)
        self._signal(pid, signal.SIGTERM)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not self._alive(pid):
                self._reap()
                self._remove_pid_file()
                return True
            time.sleep(0.1)
        self._signal(pid, signal.SIGKILL)
        time.sleep(0.2)
        self._reap()
        self._remove_pid_file()
        return not self._alive(pid)

    def restart(self, timeout: float = 10.0) -> int:
        """Stop the service if needed and start it again."""
        self.stop(timeout=timeout)
        return self.start()

    def cleanup(self) -> None:
        """Release resources and stop a service that this supervisor started."""
        if self._child is not None and self._child.poll() is None:
            self.stop(timeout=5.0)
        self._reap()
        self._close_log()

    def _reap(self) -> None:
        if self._child is None:
            return
        if self._child.poll() is None:
            return
        try:
            self._child.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass

    def _close_log(self) -> None:
        handle, self._log_handle = self._log_handle, None
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass

    @staticmethod
    def _signal(pid: Optional[int], sig: int) -> None:
        if not pid or not ServiceSupervisor._pid_alive(pid):
            return
        try:
            os.killpg(os.getpgid(pid), sig)
        except (OSError, AttributeError):
            try:
                os.kill(pid, sig)
            except OSError:
                pass

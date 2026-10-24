"""Shared helpers for the Toney test suite."""

import json
import os
import socket
import sys
import threading

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


class Error:
    """Marker that makes the fake server answer with ok: false."""

    def __init__(self, message):
        self.message = message


class FakeServer:
    """A tiny in-process implementation of the control protocol."""

    def __init__(self, path, commands=None, raw=None):
        self.path = path
        self.commands = dict(commands or {})
        self.raw = raw
        self.requests = []
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(path)
        self._sock.listen(8)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        try:
            os.unlink(self.path)
        except OSError:
            pass
        self._thread.join(timeout=2)

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        buffer = b""
        with conn:
            while True:
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    if self.raw is not None:
                        try:
                            conn.sendall(self.raw)
                        except OSError:
                            return
                        continue
                    request = json.loads(line.decode("utf-8"))
                    self.requests.append(request)
                    reply = json.dumps(self._respond(request)).encode("utf-8") + b"\n"
                    try:
                        conn.sendall(reply)
                    except OSError:
                        return

    def _respond(self, request):
        cmd = request.get("cmd")
        if cmd in self.commands:
            handler = self.commands[cmd]
            data = handler(request.get("params") or {}) if callable(handler) else handler
            if isinstance(data, Error):
                return {
                    "id": request.get("id"),
                    "ok": False,
                    "error": data.message,
                }
            return {"id": request.get("id"), "ok": True, "data": data}
        return {
            "id": request.get("id"),
            "ok": False,
            "error": "unknown command: {0}".format(cmd),
        }


def refused_socket(path):
    """Leave a socket file behind that nothing listens on."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(path)
    sock.close()
    return path

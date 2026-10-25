"""The control socket.

The TUI talks to the service through this Unix socket, and nothing else. One
JSON object per line in each direction.
"""

import json
import os
import socketserver
import threading

MAX_LINE = 1024 * 1024


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        service = self.server.service
        while True:
            try:
                line = self.rfile.readline(MAX_LINE)
            except OSError:
                return
            if not line:
                return
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                self._send({"id": None, "ok": False, "error": "invalid request: %s" % exc})
                continue
            if not isinstance(request, dict):
                self._send({"id": None, "ok": False, "error": "invalid request: expected an object"})
                continue
            ident = request.get("id")
            cmd = request.get("cmd")
            params = request.get("params") or {}
            try:
                data = service.dispatch(cmd, params)
            except Exception as exc:
                self._send({"id": ident, "ok": False, "error": str(exc) or exc.__class__.__name__})
                continue
            self._send({"id": ident, "ok": True, "data": data})

    def _send(self, payload):
        try:
            self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
            self.wfile.flush()
        except OSError:
            pass


class _UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


class ControlServer:
    """Serves the control protocol on a Unix domain socket."""

    def __init__(self, service, path):
        self.service = service
        self.path = os.path.abspath(os.path.expanduser(path))
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if os.path.exists(self.path):
            try:
                os.unlink(self.path)
            except OSError:
                pass
        self.server = _UnixServer(self.path, _Handler)
        self.server.service = service
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        try:
            self.server.shutdown()
        except Exception:
            pass
        try:
            self.server.server_close()
        except Exception:
            pass
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
        except OSError:
            pass

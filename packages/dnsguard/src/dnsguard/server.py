"""The DNS listeners.

UDP is the normal transport; TCP is there because answers that do not fit in
a UDP datagram have to be re-fetched over TCP, and because some clients only
speak TCP.
"""

import socket
import socketserver
import struct
import threading


class _UdpHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        response = self.server.service.handle_query(data, self.client_address[0])
        if response:
            try:
                sock.sendto(response, self.client_address)
            except OSError:
                pass


class _TcpHandler(socketserver.BaseRequestHandler):
    def handle(self):
        header = self._read(2)
        if not header:
            return
        length = struct.unpack(">H", header)[0]
        data = self._read(length)
        if not data:
            return
        response = self.server.service.handle_query(data, self.client_address[0])
        if response:
            try:
                self.request.sendall(struct.pack(">H", len(response)) + response)
            except OSError:
                pass

    def _read(self, count):
        chunks = []
        remaining = count
        while remaining > 0:
            try:
                chunk = self.request.recv(remaining)
            except OSError:
                return None
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


class _UdpServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True
    daemon_threads = True


class _TcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class DnsListener:
    """Owns the UDP and TCP sockets."""

    def __init__(self, service, host, port):
        self.service = service
        self.host = host
        self.port = port
        self.udp = _UdpServer((host, port), _UdpHandler)
        self.udp.service = service
        self.tcp = _TcpServer((host, port), _TcpHandler)
        self.tcp.service = service
        self.threads = []

    def start(self):
        for server in (self.udp, self.tcp):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)

    def stop(self):
        for server in (self.udp, self.tcp):
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass

    @property
    def bound_port(self):
        return self.udp.server_address[1]

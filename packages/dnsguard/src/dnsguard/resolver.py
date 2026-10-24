"""Upstream forwarding.

Plain DNS over UDP with a TCP fallback when the answer is truncated, plus an
optional DNS-over-HTTPS upstream (RFC 8484, POST with
``application/dns-message``). Answers are cached in memory for a short time so
repeated lookups cost nothing.
"""

import os
import socket
import struct
import threading
import time
import urllib.error
import urllib.request

from . import wire


class ResolverError(RuntimeError):
    """Raised when no upstream could answer."""


class Cache:
    """A small TTL cache of raw DNS answers."""

    def __init__(self, size=4096):
        self.size = max(0, int(size))
        self._entries = {}
        self._lock = threading.Lock()

    def get(self, key):
        if not self.size:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires, payload = entry
            if expires <= time.time():
                self._entries.pop(key, None)
                return None
            return payload

    def put(self, key, payload, ttl):
        if not self.size or ttl <= 0:
            return
        with self._lock:
            if len(self._entries) >= self.size:
                oldest = min(self._entries, key=lambda k: self._entries[k][0])
                self._entries.pop(oldest, None)
            self._entries[key] = (time.time() + ttl, payload)

    def clear(self):
        with self._lock:
            self._entries.clear()

    def __len__(self):
        with self._lock:
            return len(self._entries)


class Resolver:
    """Forwards queries to the configured upstream resolvers."""

    def __init__(self, servers=None, doh=None, timeout=4.0, cache_size=4096,
                 cache_ttl_s=300):
        self.servers = list(servers or [])
        self.doh = doh
        self.timeout = float(timeout)
        self.cache_ttl_s = int(cache_ttl_s)
        self.cache = Cache(cache_size)
        self.lock = threading.Lock()

    def configure(self, servers=None, doh=None, timeout=None, cache_size=None,
                  cache_ttl_s=None):
        with self.lock:
            if servers is not None:
                self.servers = list(servers)
            if doh is not None:
                self.doh = doh or None
            if timeout is not None:
                self.timeout = float(timeout)
            if cache_size is not None:
                self.cache = Cache(cache_size)
            if cache_ttl_s is not None:
                self.cache_ttl_s = int(cache_ttl_s)

    def query(self, qname, qtype, wire_query=None, transaction_id=None):
        """Resolve a name and return the raw response bytes.

        Returns (payload, from_cache).
        """
        key = (qname.lower().rstrip("."), qtype)
        cached = self.cache.get(key)
        if cached is not None:
            return cached, True

        query = wire_query
        if query is None:
            query = wire.build_query(transaction_id if transaction_id is not None else 0,
                                     qname, qtype)

        with self.lock:
            servers = list(self.servers)
            doh = self.doh

        payload = None
        if doh:
            payload = self._query_doh(doh, query)
        if payload is None:
            for server in servers:
                payload = self._query_udp(server, query)
                if payload is not None:
                    break
        if payload is None:
            raise ResolverError("no upstream answered %s" % qname)

        if wire.rcode(payload) == 0:
            self.cache.put(key, payload, self.cache_ttl_s)
        return payload, False

    def _query_udp(self, server, query):
        host, _, port = server.partition(":")
        port = int(port) if port.isdigit() else 53
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except OSError:
            return None
        try:
            sock.settimeout(self.timeout)
            sock.sendto(query, (host, port))
            data, _ = sock.recvfrom(65535)
        except OSError:
            return None
        finally:
            sock.close()
        if wire.is_truncated(data):
            return self._query_tcp(host, port, query)
        return data

    def _query_tcp(self, host, port, query):
        try:
            sock = socket.create_connection((host, port), timeout=self.timeout)
        except OSError:
            return None
        try:
            sock.sendall(struct.pack(">H", len(query)) + query)
            header = self._read_exactly(sock, 2)
            if not header:
                return None
            length = struct.unpack(">H", header)[0]
            body = self._read_exactly(sock, length)
            if body is None:
                return None
            return body
        except OSError:
            return None
        finally:
            sock.close()

    @staticmethod
    def _read_exactly(sock, count):
        chunks = []
        remaining = count
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _query_doh(self, url, query):
        request = urllib.request.Request(
            url,
            data=query,
            headers={
                "Content-Type": "application/dns-message",
                "Accept": "application/dns-message",
                "User-Agent": "dnsguard/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def describe(self):
        return {
            "servers": list(self.servers),
            "doh": self.doh,
            "timeout_s": self.timeout,
            "cache_size": self.cache.size,
            "cache_ttl_s": self.cache_ttl_s,
        }

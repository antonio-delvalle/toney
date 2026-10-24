"""Query log with daily rotation, size cap and expiry.

One JSON object per line. A new file is started every day, files are swept
once they are older than the retention window, and a file that grows past the
size cap is compressed and rolled over so a single day can never fill the
disk.
"""

import gzip
import json
import os
import shutil
import threading
import time

SUFFIX = ".jsonl"
ROLLED_SUFFIX = ".jsonl.1.gz"


class QueryLog:
    """Append-only query log."""

    def __init__(self, directory, retention_days=5, max_bytes=64 * 1024 * 1024,
                 clock=time.time):
        self.directory = os.path.abspath(os.path.expanduser(directory))
        self.retention_days = max(1, int(retention_days))
        self.max_bytes = max(1024, int(max_bytes))
        self.clock = clock
        self.lock = threading.Lock()
        self._handle = None
        self._path = None
        os.makedirs(self.directory, exist_ok=True)

    def _today(self):
        return time.strftime("%Y-%m-%d", time.gmtime(self.clock()))

    def current_path(self):
        return os.path.join(self.directory, self._today() + SUFFIX)

    def _open(self):
        path = self.current_path()
        if self._handle is not None and self._path == path:
            return
        self._close_handle()
        self._handle = open(path, "ab")
        self._path = path

    def _close_handle(self):
        if self._handle is not None:
            try:
                self._handle.flush()
                self._handle.close()
            except OSError:
                pass
            self._handle = None
            self._path = None

    def write(self, record):
        """Append one record. Returns the path it was written to."""
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        raw = line.encode("utf-8")
        with self.lock:
            self._open()
            if self._handle.tell() + len(raw) > self.max_bytes:
                self._roll()
                self._open()
            self._handle.write(raw)
            self._handle.flush()
            return self._path

    def _roll(self):
        """Compress the current file and start a new one."""
        path = self._path
        if not path or not os.path.exists(path):
            return
        self._close_handle()
        rolled = path + ".1.gz"
        try:
            if os.path.exists(rolled):
                os.unlink(rolled)
            with open(path, "rb") as source, gzip.open(rolled, "wb") as target:
                shutil.copyfileobj(source, target)
            os.unlink(path)
        except OSError:
            pass

    def sweep(self):
        """Delete files that fall outside the retention window."""
        removed = []
        cutoff = self._cutoff_date()
        with self.lock:
            self._close_handle()
        try:
            names = os.listdir(self.directory)
        except OSError:
            return removed
        for name in names:
            path = os.path.join(self.directory, name)
            if not os.path.isfile(path):
                continue
            if not (name.endswith(SUFFIX) or name.endswith(ROLLED_SUFFIX)):
                continue
            date = self._date_of(name)
            if date is None:
                if self._too_old(path):
                    self._remove(path)
                    removed.append(path)
                continue
            if date < cutoff:
                self._remove(path)
                removed.append(path)
        return removed

    def _cutoff_date(self):
        now = time.gmtime(self.clock())
        return time.strftime("%Y-%m-%d", time.gmtime(time.time() - (self.retention_days - 1) * 86400))

    def _too_old(self, path):
        try:
            age = self.clock() - os.path.getmtime(path)
        except OSError:
            return False
        return age > self.retention_days * 86400

    @staticmethod
    def _date_of(name):
        base = name.split(".")[0]
        if len(base) != 10 or base.count("-") != 2:
            return None
        try:
            time.strptime(base, "%Y-%m-%d")
        except ValueError:
            return None
        return base

    @staticmethod
    def _remove(path):
        try:
            os.unlink(path)
        except OSError:
            pass

    def files(self):
        """Describe the log files on disk."""
        out = []
        try:
            names = sorted(os.listdir(self.directory))
        except OSError:
            return out
        for name in names:
            path = os.path.join(self.directory, name)
            if not os.path.isfile(path):
                continue
            if not (name.endswith(SUFFIX) or name.endswith(ROLLED_SUFFIX)):
                continue
            try:
                stat = os.stat(path)
            except OSError:
                continue
            out.append({
                "path": path,
                "bytes": stat.st_size,
                "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
            })
        return out

    def total_bytes(self):
        return sum(f["bytes"] for f in self.files())

    def tail(self, limit=100, needle=None, client=None):
        """Return the most recent records, newest first."""
        records = []
        try:
            names = sorted(
                (n for n in os.listdir(self.directory) if n.endswith(SUFFIX)),
                reverse=True)
        except OSError:
            return records
        for name in names:
            path = os.path.join(self.directory, name)
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    lines = handle.readlines()
            except OSError:
                continue
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if needle and needle not in str(record.get("name", "")):
                    continue
                if client and record.get("client") != client:
                    continue
                records.append(record)
                if len(records) >= limit:
                    return records
        return records

    def close(self):
        with self.lock:
            self._close_handle()

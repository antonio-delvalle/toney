"""Service state: rules, resolver, log, counters.

Everything the control socket can report or change lives here, and both the
DNS listeners and the control socket talk to this one object.
"""

import os
import threading
import time
from collections import Counter, deque

from . import rules as rules_mod
from . import wire
from .querylog import QueryLog
from .resolver import Resolver, ResolverError
from .router import RouterDriver, RouterError

VERSION = "0.1.0"
RECENT_LIMIT = 5000


class Service:
    """The filtering service."""

    def __init__(self, config):
        self.config = config
        self.started_at = time.time()
        self.lock = threading.RLock()
        self.counters = Counter()
        self.clients = {}
        self.recent = deque(maxlen=RECENT_LIMIT)
        self.minutes = {}
        self.rules = rules_mod.RuleSet()
        self.log = QueryLog(
            config.expanded("log_dir"),
            retention_days=config.get("retention_days"),
            max_bytes=config.get("log_max_bytes"),
        )
        self.router = RouterDriver(config.get("router") or {})
        self.resolver = Resolver(
            servers=config.get("upstream"),
            doh=config.get("doh"),
            timeout=config.get("timeout_s"),
            cache_size=config.get("cache_size"),
            cache_ttl_s=config.get("cache_ttl_s"),
        )
        self._stopping = False

    # -- rules ------------------------------------------------------------- #

    def load_rules(self, paths=None):
        """Load the rule files and return the number of rules."""
        paths = paths if paths is not None else self.config.get("rules")
        loaded = rules_mod.load_rules(paths)
        loaded.loaded_at = time.time()
        with self.lock:
            self.rules = loaded
        return loaded

    def reload_rules(self):
        started = time.time()
        loaded = self.load_rules()
        return {
            "count": loaded.count,
            "loaded_at": _iso(loaded.loaded_at or started),
            "duration_ms": int((time.time() - started) * 1000),
            "sources": list(loaded.sources),
        }

    # -- query handling ---------------------------------------------------- #

    def handle_query(self, data, client):
        """Answer one query. Returns the response bytes or None."""
        try:
            query = wire.parse_query(data)
        except wire.WireError:
            self.counters["errors"] += 1
            return None

        name = query["qname"]
        decision, rule = self.rules.match(name)

        if decision == rules_mod.BLOCK:
            response = wire.build_response(query["id"], query["flags"],
                                           query["question_bytes"], rcode=3)
            self._record(client, name, query["qtype"], "block",
                         rule.pattern if rule else None)
            return response

        try:
            payload, cached = self.resolver.query(
                name, query["qtype"], wire_query=data, transaction_id=query["id"])
        except ResolverError:
            self.counters["errors"] += 1
            self._record(client, name, query["qtype"], "error", None)
            return wire.build_response(query["id"], query["flags"],
                                       query["question_bytes"], rcode=2)

        self._record(client, name, query["qtype"], "cache" if cached else "allow",
                     None)
        return wire.set_id(payload, query["id"])

    def _record(self, client, name, qtype, decision, rule):
        now = time.time()
        record = {
            "ts": _iso(now),
            "client": client,
            "name": name + ".",
            "type": _qtype_name(qtype),
            "decision": decision,
            "rule": rule,
        }
        with self.lock:
            self.counters["total"] += 1
            self.counters[decision] += 1
            bucket = self.clients.setdefault(client, Counter())
            bucket["total"] += 1
            if decision == "block":
                bucket["blocked"] += 1
            elif decision in ("allow", "cache"):
                bucket["allowed"] += 1
            self.recent.append(record)
            minute = int(now // 60) * 60
            slot = self.minutes.setdefault(minute, Counter())
            slot["total"] += 1
            slot[decision] += 1
            cutoff = int((now - 3600) // 60) * 60
            for stale in [k for k in self.minutes if k < cutoff]:
                self.minutes.pop(stale, None)
        try:
            self.log.write(record)
        except OSError:
            pass

    # -- reporting --------------------------------------------------------- #

    def status(self):
        with self.lock:
            counters = {
                "total": self.counters.get("total", 0),
                "allowed": self.counters.get("allow", 0) + self.counters.get("cache", 0),
                "blocked": self.counters.get("block", 0),
                "cached": self.counters.get("cache", 0),
                "errors": self.counters.get("error", 0),
            }
            clients = {
                client: {
                    "total": counts.get("total", 0),
                    "blocked": counts.get("blocked", 0),
                    "allowed": counts.get("allowed", 0),
                }
                for client, counts in sorted(self.clients.items())
            }
            rules = self.rules
        return {
            "name": "dnsguard",
            "version": VERSION,
            "pid": os.getpid(),
            "started_at": _iso(self.started_at),
            "uptime_s": int(time.time() - self.started_at),
            "listen": self.config.get("listen"),
            "upstream": list(self.config.get("upstream") or []),
            "doh": self.config.get("doh"),
            "config_path": self.config.path,
            "rules": {
                "count": rules.count,
                "block": rules.block_count,
                "allow": rules.allow_count,
                "loaded_at": _iso(rules.loaded_at or self.started_at),
                "sources": list(rules.sources),
            },
            "counters": counters,
            "clients": clients,
            "log": {
                "dir": self.log.directory,
                "retention_days": self.log.retention_days,
                "max_bytes": self.log.max_bytes,
                "total_bytes": self.log.total_bytes(),
                "files": self.log.files(),
            },
        }

    def stats(self, window_s=300):
        now = time.time()
        cutoff = int((now - window_s) // 60) * 60
        buckets = []
        with self.lock:
            for minute in sorted(k for k in self.minutes if k >= cutoff):
                slot = self.minutes[minute]
                buckets.append({
                    "t": _iso(minute),
                    "total": slot.get("total", 0),
                    "blocked": slot.get("block", 0),
                    "allowed": slot.get("allow", 0) + slot.get("cache", 0),
                })
            blocked = Counter()
            allowed = Counter()
            for record in self.recent:
                name = record.get("name", "")
                if record.get("decision") == "block":
                    blocked[name] += 1
                elif record.get("decision") in ("allow", "cache"):
                    allowed[name] += 1
        return {
            "window_s": window_s,
            "buckets": buckets,
            "top_blocked": [{"name": n, "count": c} for n, c in blocked.most_common(20)],
            "top_allowed": [{"name": n, "count": c} for n, c in allowed.most_common(20)],
        }

    def tail_logs(self, limit=100, needle=None, client=None):
        return self.log.tail(limit=limit, needle=needle, client=client)

    def log_clients(self, limit=500):
        """The addresses seen in the query log, the most recent ones first."""
        return self.log.clients(limit=limit)

    def config_dict(self):
        return self.config.to_dict()

    def apply_config(self, partial):
        changed = self.config.apply(partial)
        if "upstream" in changed or "doh" in changed:
            self.resolver.configure(
                servers=self.config.get("upstream"),
                doh=self.config.get("doh"),
                timeout=self.config.get("timeout_s"),
                cache_size=self.config.get("cache_size"),
                cache_ttl_s=self.config.get("cache_ttl_s"),
            )
        if "rules" in changed:
            self.load_rules()
        if "retention_days" in changed or "log_max_bytes" in changed:
            self.log.retention_days = self.config.get("retention_days")
            self.log.max_bytes = self.config.get("log_max_bytes")
        self.persist_config()
        return changed

    def persist_config(self):
        """Write the effective configuration back to the file it was read from.

        Without this a change made over the control socket lives only in the
        running process: the next start reads the file again and the change is
        gone.  The file stays the single source of truth, so it has to record
        what the socket just did.
        """
        if not self.config.path:
            return False
        try:
            self.config.save()
        except (OSError, ValueError):
            return False
        return True

    def sweep_logs(self):
        return self.log.sweep()

    # -- control protocol -------------------------------------------------- #

    def dispatch(self, cmd, params):
        """Run one control command and return its data payload."""
        if not isinstance(params, dict):
            raise ValueError("invalid params: expected an object")
        if cmd == "status":
            return self.status()
        if cmd == "stats":
            window = int(params.get("window_s", 300))
            return self.stats(max(1, min(window, 86400)))
        if cmd == "rules.list":
            with self.lock:
                return {"count": self.rules.count, "rules": self.rules.as_list()}
        if cmd == "rules.reload":
            return self.reload_rules()
        if cmd == "rules.set":
            path = params.get("path")
            if not path:
                raise ValueError("invalid params: path is required")
            expanded = os.path.abspath(os.path.expanduser(path))
            if not os.path.isfile(expanded):
                raise ValueError("rules: no such file: %s" % expanded)
            target = os.path.join(self.log.directory, "rules.blocklist")
            with open(expanded, encoding="utf-8") as source:
                payload = source.read()
            with open(target, "w", encoding="utf-8") as destination:
                destination.write(payload)
            self.apply_config({"rules": [target]})
            return self.reload_rules()
        if cmd == "logs.tail":
            limit = int(params.get("limit", 100))
            limit = max(1, min(limit, 5000))
            return {"lines": self.tail_logs(limit=limit,
                                            needle=params.get("filter"),
                                            client=params.get("client"))}
        if cmd == "logs.clients":
            limit = int(params.get("limit", 500))
            limit = max(1, min(limit, 5000))
            return {"clients": self.log_clients(limit=limit)}
        if cmd == "config.get":
            return self.config_dict()
        if cmd == "config.set":
            changed = self.apply_config(params)
            return {"changed": changed, "config": self.config_dict()}
        if cmd == "upstream.set":
            servers = params.get("servers")
            if servers is not None and not isinstance(servers, list):
                raise ValueError("invalid params: servers must be a list")
            self.apply_config({"upstream": servers or [],
                               "doh": params.get("doh") or None})
            return {"upstream": list(self.config.get("upstream") or []),
                    "doh": self.config.get("doh")}
        if cmd == "router.status":
            return self.router.status(self.rules.rules)
        if cmd == "router.deploy":
            return self.router.deploy(self.rules.rules)
        if cmd == "router.rollback":
            return self.router.rollback()
        if cmd == "shutdown":
            threading.Thread(target=self.request_shutdown, daemon=True).start()
            return {"stopping": True}
        raise ValueError("unknown command: %s" % cmd)

    def request_shutdown(self):
        if getattr(self, "_shutdown_hook", None):
            self._shutdown_hook()

    def stop(self):
        self._stopping = True
        self.log.close()


def _iso(timestamp):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))


_QTYPES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX", 16: "TXT",
           28: "AAAA", 33: "SRV", 41: "OPT", 255: "ANY"}


def _qtype_name(qtype):
    return _QTYPES.get(qtype, str(qtype))

"""Configuration handling for dnsguard.

The configuration is a small JSON document. Every value has a default, so
the service starts with no configuration at all and can be configured
entirely through the control socket afterwards.
"""

import copy
import json
import os

DEFAULTS = {
    "listen": "0.0.0.0:5353",
    "upstream": [],
    "doh": None,
    "timeout_s": 4.0,
    "cache_size": 4096,
    "cache_ttl_s": 300,
    "log_dir": "~/.local/state/toney/dnsguard",
    "retention_days": 5,
    "log_max_bytes": 64 * 1024 * 1024,
    "rules": [],
    "control": "~/.local/state/toney/dnsguard.sock",
    "router": {},
}

PATH_KEYS = ("log_dir", "control")
LIST_KEYS = ("upstream", "rules")


def system_upstream():
    """Read the resolvers configured on this machine."""
    servers = []
    try:
        with open("/etc/resolv.conf", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    servers.append(parts[1])
    except OSError:
        pass
    return servers


def default_config():
    data = copy.deepcopy(DEFAULTS)
    data["upstream"] = system_upstream()
    return data


class Config:
    """The effective configuration of a service."""

    def __init__(self, data=None, path=None):
        self.data = copy.deepcopy(default_config())
        if data:
            self.data.update(data)
        self.path = os.path.abspath(os.path.expanduser(path)) if path else None

    @classmethod
    def load(cls, path):
        expanded = os.path.expanduser(path)
        if not os.path.isfile(expanded):
            return cls(path=path)
        with open(expanded, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("configuration must be a JSON object")
        return cls(data, path=path)

    def save(self, path=None):
        target = os.path.abspath(os.path.expanduser(path or self.path))
        if not target:
            raise ValueError("no configuration path to write to")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        self.path = target
        return target

    def to_dict(self):
        return copy.deepcopy(self.data)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def expanded(self, key):
        """Return a path-valued setting with ``~`` expanded."""
        value = self.data.get(key)
        if value is None:
            return None
        return os.path.abspath(os.path.expanduser(str(value)))

    def apply(self, partial):
        """Apply a partial configuration and return the keys that changed."""
        if not isinstance(partial, dict):
            raise ValueError("configuration update must be an object")
        changed = []
        for key, value in partial.items():
            if key not in DEFAULTS:
                raise ValueError("unknown setting: %s" % key)
            if key == "control":
                raise ValueError("the control socket path cannot be changed at runtime")
            if key in LIST_KEYS and not isinstance(value, list):
                raise ValueError("%s must be a list" % key)
            if self.data.get(key) != value:
                self.data[key] = value
                changed.append(key)
        return changed

    def validate(self):
        """Raise ValueError when the configuration cannot be used."""
        listen = self.data.get("listen", "")
        if ":" not in listen:
            raise ValueError("listen must look like address:port")
        host, _, port = listen.rpartition(":")
        if not port.isdigit():
            raise ValueError("listen port must be a number")
        retention = self.data.get("retention_days")
        if not isinstance(retention, int) or retention < 1:
            raise ValueError("retention_days must be a positive integer")
        if self.data.get("log_max_bytes", 0) < 1024:
            raise ValueError("log_max_bytes must be at least 1024")
        return True

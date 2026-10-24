"""Configuration file handling for the Toney terminal UI.

The TUI keeps its own small JSON configuration file.  It never contains
service secrets: it only points at the control socket and describes how the
service process has to be started.
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, Optional

DEFAULT_CONFIG_PATH = os.path.join("~", ".config", "toney", "toney.json")
DEFAULT_CONTROL_SOCKET = os.path.join("~", ".local", "state", "toney", "dnsguard.sock")
DEFAULT_SERVICE_COMMAND = ["python3", "-m", "dnsguard", "serve"]
DEFAULT_SERVICE_CONFIG_PATH = os.path.join("~", ".config", "toney", "dnsguard.json")

DEFAULTS: Dict[str, Any] = {
    "control_socket": DEFAULT_CONTROL_SOCKET,
    "service": {
        "command": list(DEFAULT_SERVICE_COMMAND),
        "cwd": None,
        "env": {},
    },
    "config_path": DEFAULT_SERVICE_CONFIG_PATH,
    "stop_on_exit": True,
}


def default_config() -> Dict[str, Any]:
    """Return a fresh copy of the built-in defaults."""
    return copy.deepcopy(DEFAULTS)


def expand_path(path: str) -> str:
    """Expand ``~`` and environment variables in *path*."""
    if not isinstance(path, str):
        return path
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            merged[key] = _merge(current, value)
        else:
            merged[key] = value
    return merged


def normalise(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return *config* with the defaults applied and paths expanded."""
    result = _merge(default_config(), config if isinstance(config, dict) else {})
    result["control_socket"] = expand_path(result.get("control_socket") or DEFAULT_CONTROL_SOCKET)
    service = result.get("service")
    if not isinstance(service, dict):
        service = {}
    command = service.get("command")
    if isinstance(command, str):
        command = [command]
    elif not isinstance(command, list):
        command = list(DEFAULT_SERVICE_COMMAND)
    else:
        command = [str(part) for part in command]
    cwd = service.get("cwd")
    env = service.get("env")
    manager = service.get("manager")
    if isinstance(manager, dict):
        manager = {
            str(key): [str(part) for part in value]
            if isinstance(value, (list, tuple))
            else [str(value)]
            for key, value in manager.items()
        }
    else:
        manager = {}
    result["service"] = {
        "command": command,
        "cwd": expand_path(cwd) if cwd else None,
        "env": {str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else {},
        "manager": manager,
    }
    result["stop_on_exit"] = bool(result.get("stop_on_exit", True))
    return result


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the TUI configuration.

    A missing or unreadable file is not an error: the built-in defaults are
    returned instead so that the UI always starts.
    """
    target = expand_path(path or DEFAULT_CONFIG_PATH)
    config = default_config()
    try:
        with open(target, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return normalise(config)
    if isinstance(loaded, dict):
        config = _merge(config, loaded)
    return normalise(config)


def save_config(config: Dict[str, Any], path: Optional[str] = None) -> str:
    """Write *config* to disk and return the path that was written."""
    target = expand_path(path or DEFAULT_CONFIG_PATH)
    directory = os.path.dirname(target)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = normalise(config)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return target

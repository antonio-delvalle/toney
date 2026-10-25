"""Command line entry point for Toney."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

from toney import __version__
from toney.client import ControlClient, ToneyError
from toney.config import DEFAULT_CONFIG_PATH, load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toney",
        description="Toney, a terminal UI that manages the dnsguard DNS filtering service.",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="path to the Toney configuration file (default: {0})".format(
            DEFAULT_CONFIG_PATH
        ),
    )
    parser.add_argument(
        "--control",
        metavar="PATH",
        default=None,
        help="path to the dnsguard control socket (overrides the configuration file)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check whether the service is reachable, print one line and exit",
    )
    parser.add_argument("--version", action="version", version="toney {0}".format(__version__))
    return parser


def check_service(socket_path: str) -> int:
    """Print a one line health summary of the service.  Returns 0 or 1."""
    client = ControlClient(socket_path, timeout=3.0, connect_timeout=1.0, retries=0)
    try:
        with client:
            data = client.status()
    except (ToneyError, OSError) as exc:
        print("toney: {0}".format(exc))
        return 1
    data = data or {}
    print(
        "toney: service reachable ({0} {1}, pid {2}, socket {3})".format(
            data.get("name", "dnsguard"),
            data.get("version", "?"),
            data.get("pid", "?"),
            os.path.expanduser(socket_path),
        )
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config: Dict[str, Any] = load_config(args.config)
    if args.control:
        config["control_socket"] = os.path.expanduser(args.control)
    if args.check:
        return check_service(config["control_socket"])
    try:
        from toney.app import run_app

        return run_app(config)
    except KeyboardInterrupt:
        return 130
    except RuntimeError as exc:
        print("toney: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

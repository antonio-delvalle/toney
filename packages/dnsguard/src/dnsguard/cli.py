"""Command line entry point for dnsguard."""

import argparse
import json
import os
import signal
import sys
import threading
import time

from .config import Config
from .control import ControlServer
from .server import DnsListener
from .service import Service, VERSION

DEFAULT_CONFIG = os.path.join(
    os.path.expanduser("~"), ".config", "toney", "dnsguard.json")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="dnsguard",
        description="A DNS filtering service with a query log and a control socket.")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="path to the JSON configuration file")
    sub = parser.add_subparsers(dest="command")

    def add(name, help_text):
        parser_sub = sub.add_parser(name, help=help_text)
        parser_sub.add_argument("--config", dest="config_sub", default=None,
                                help="path to the JSON configuration file")
        return parser_sub

    serve = add("serve", "run the service in the foreground")
    serve.add_argument("--listen", help="override the listen address, host:port")
    serve.add_argument("--upstream", help="comma separated upstream resolvers")
    serve.add_argument("--rules", help="comma separated rule files")
    serve.add_argument("--control", help="override the control socket path")

    add("config", "print the effective configuration")
    add("rules", "print the loaded rules")

    logs = add("logs", "print recent query log records")
    logs.add_argument("--limit", type=int, default=20)

    add("sweep", "delete log files outside the retention window")
    add("version", "print the version")

    router = add("router", "deploy or roll back the rule set on a router")
    router.add_argument("action", choices=["status", "deploy", "rollback"],
                         help="what to do on the router")
    return parser


def load_config(args):
    path = getattr(args, "config_sub", None) or args.config
    config = Config.load(path)
    if getattr(args, "listen", None):
        config.data["listen"] = args.listen
    if getattr(args, "upstream", None):
        config.data["upstream"] = [s.strip() for s in args.upstream.split(",") if s.strip()]
    if getattr(args, "rules", None):
        config.data["rules"] = [s.strip() for s in args.rules.split(",") if s.strip()]
    if getattr(args, "control", None):
        config.data["control"] = args.control
    config.validate()
    return config


def serve(args):
    config = load_config(args)
    service = Service(config)
    try:
        service.load_rules()
    except (OSError, FileNotFoundError) as exc:
        print("dnsguard: cannot load rules: %s" % exc, file=sys.stderr)
        return 2

    host, _, port = config.get("listen").rpartition(":")
    listener = DnsListener(service, host or "0.0.0.0", int(port))
    listener.start()

    control = ControlServer(service, config.expanded("control"))
    control.start()

    stopping = threading.Event()

    def stop(signum=None, frame=None):
        stopping.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    service._shutdown_hook = stop

    sweep_timer = threading.Thread(target=_sweeper, args=(service, stopping), daemon=True)
    sweep_timer.start()

    print("dnsguard %s listening on %s:%d" % (VERSION, host or "0.0.0.0", listener.bound_port))
    print("dnsguard control socket: %s" % control.path)
    print("dnsguard rules loaded: %d from %d file(s)"
          % (service.rules.count, len(service.rules.sources)))
    sys.stdout.flush()

    try:
        while not stopping.is_set():
            stopping.wait(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        print("dnsguard: shutting down")
        listener.stop()
        control.stop()
        service.stop()
    return 0


def _sweeper(service, stopping):
    while not stopping.wait(3600):
        try:
            service.sweep_logs()
        except OSError:
            pass


def show_config(args):
    config = load_config(args)
    print(json.dumps(config.to_dict(), indent=2, sort_keys=True))
    return 0


def show_rules(args):
    config = load_config(args)
    service = Service(config)
    try:
        service.load_rules()
    except (OSError, FileNotFoundError) as exc:
        print("dnsguard: cannot load rules: %s" % exc, file=sys.stderr)
        return 2
    for rule in service.rules.rules:
        print("%-8s %-40s %s:%d" % (rule.action, rule.pattern,
                                     os.path.basename(rule.source or "?"), rule.line))
    print("%d rule(s) from %d file(s)" % (service.rules.count, len(service.rules.sources)))
    return 0


def show_logs(args):
    config = load_config(args)
    service = Service(config)
    for record in service.tail_logs(limit=args.limit):
        print(json.dumps(record, sort_keys=True))
    return 0


def sweep(args):
    config = load_config(args)
    service = Service(config)
    removed = service.sweep_logs()
    for path in removed:
        print("removed %s" % path)
    print("%d file(s) removed" % len(removed))
    return 0


def router(args):
    config = load_config(args)
    service = Service(config)
    try:
        service.load_rules()
    except (OSError, FileNotFoundError) as exc:
        print("dnsguard: cannot load rules: %s" % exc, file=sys.stderr)
        return 2
    if args.action == "status":
        result = service.router.status(service.rules.rules)
    elif args.action == "deploy":
        result = service.router.deploy(service.rules.rules)
    else:
        result = service.router.rollback()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "serve"
    handlers = {
        "serve": serve,
        "config": show_config,
        "rules": show_rules,
        "logs": show_logs,
        "sweep": sweep,
        "router": router,
        "version": lambda a: (print(VERSION), 0)[1],
    }
    handler = handlers.get(command)
    if handler is None:
        parser.print_help()
        return 2
    try:
        return handler(args)
    except ValueError as exc:
        print("dnsguard: %s" % exc, file=sys.stderr)
        return 2
    except OSError as exc:
        print("dnsguard: %s" % exc, file=sys.stderr)
        return 1

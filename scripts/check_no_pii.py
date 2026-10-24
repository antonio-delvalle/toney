#!/usr/bin/env python3
"""Fail the build when the tree contains anything that looks personal.

The repository is public, so it must not carry private addresses, personal
paths, e-mail addresses or device identifiers. The patterns below are built
from fragments so that this file does not trip its own checks.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "build", "dist"}
SKIP_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".gz", ".zip", ".ico")
ALLOWED_EMAILS = ("example.com", "example.org", "example.net", "noreply.github.com")
ALLOWED_MACS = ("00:11:22:33:44:55", "02:00:00:00:00:01")

PRIVATE_IP = re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
                         r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
                         r"|192\.168\.\d{1,3}\.\d{1,3})\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAC = re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")
HOME_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")
UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
                  r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


def looks_like_placeholder(text):
    lowered = text.lower()
    return any(token in lowered for token in ("example", "placeholder", "yourname",
                                              "username", "xxxx", "192.0.2"))


def check_file(path, relative):
    problems = []
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError):
        return problems
    for number, line in enumerate(text.splitlines(), start=1):
        if looks_like_placeholder(line):
            continue
        for match in PRIVATE_IP.finditer(line):
            problems.append("%s:%d private address %s" % (relative, number, match.group()))
        for match in EMAIL.finditer(line):
            if not any(domain in match.group().lower() for domain in ALLOWED_EMAILS):
                problems.append("%s:%d e-mail address %s" % (relative, number, match.group()))
        for match in MAC.finditer(line):
            if match.group().lower() not in ALLOWED_MACS:
                problems.append("%s:%d hardware address %s" % (relative, number, match.group()))
        for match in HOME_PATH.finditer(line):
            problems.append("%s:%d personal path %s" % (relative, number, match.group()))
        for match in UUID.finditer(line):
            problems.append("%s:%d identifier %s" % (relative, number, match.group()))
    return problems


def main():
    problems = []
    checked = 0
    for directory, subdirectories, files in os.walk(ROOT):
        subdirectories[:] = [d for d in subdirectories if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.endswith(SKIP_SUFFIX):
                continue
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, ROOT)
            problems.extend(check_file(path, relative))
            checked += 1
    for problem in problems:
        print(problem)
    print("checked %d file(s), %d problem(s)" % (checked, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

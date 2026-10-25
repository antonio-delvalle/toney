#!/usr/bin/env python3
"""Fail the build when a package imports something outside the standard library.

The dnsguard service promises to run with nothing but a Python interpreter, so
that check stays strict.  The toney interface is built with Textual, so it is
allowed to import Textual and the modules Textual itself pulls in.

Run it without arguments to check every package.
"""

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGES = ("dnsguard", "toney")
LOCAL = set(PACKAGES)

# The dependency closure of textual, spelled as module roots.
TEXTUAL_ALLOWLIST = frozenset(
    {
        "textual",
        "rich",
        "markdown_it",
        "mdit_py_plugins",
        "linkify_it",
        "platformdirs",
        "pygments",
        "typing_extensions",
    }
)

ALLOWED = {
    "dnsguard": frozenset(),
    "toney": TEXTUAL_ALLOWLIST,
}


def module_roots(tree):
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def check_package(package, stdlib):
    """Return the list of imports that the package is not allowed to make."""
    allowed = ALLOWED.get(package, frozenset())
    problems = []
    base = os.path.join(ROOT, "packages", package, "src")
    for directory, _, files in os.walk(base):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for root in sorted(module_roots(tree)):
                if root in LOCAL or root in stdlib or root in allowed:
                    continue
                problems.append("%s: imports %s" % (os.path.relpath(path, ROOT), root))
    return problems


def main():
    stdlib = set(sys.stdlib_module_names)
    problems = []
    checked = 0
    for package in PACKAGES:
        base = os.path.join(ROOT, "packages", package, "src")
        for directory, _, files in os.walk(base):
            checked += len([name for name in files if name.endswith(".py")])
        problems.extend(check_package(package, stdlib))
    for problem in problems:
        print(problem)
    print("checked %d file(s), %d problem(s)" % (checked, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

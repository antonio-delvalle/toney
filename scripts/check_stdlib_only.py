#!/usr/bin/env python3
"""Fail the build when a package imports something outside the standard library.

Both applications promise to run with nothing but a Python interpreter. This
check keeps that promise honest.
"""

import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGES = ("dnsguard", "toney")
LOCAL = set(PACKAGES)


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


def main():
    stdlib = set(sys.stdlib_module_names)
    problems = []
    checked = 0
    for package in PACKAGES:
        base = os.path.join(ROOT, "packages", package, "src")
        for directory, _, files in os.walk(base):
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(directory, name)
                with open(path, encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                checked += 1
                for root in sorted(module_roots(tree)):
                    if root in LOCAL or root in stdlib:
                        continue
                    problems.append("%s: imports %s" % (os.path.relpath(path, ROOT), root))
    for problem in problems:
        print(problem)
    print("checked %d file(s), %d problem(s)" % (checked, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

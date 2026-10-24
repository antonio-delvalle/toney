"""Rule parsing and matching.

The rule syntax is Adblock-Plus flavoured, so lists written for Pi-hole,
AdGuard Home or NextDNS can be used unchanged:

    ||ads.example.net^     block a domain and every subdomain
    |exact.example.net|    block one exact name
    @@||cdn.example.net^   never block (keep), wins over block rules
    /^acr[0-9]+\\.example$/  block when a regular expression matches

Lines starting with ``!`` or ``#`` are comments.
"""

import os
import re

BLOCK = "block"
ALLOW = "allow"

DOMAIN = "domain"
EXACT = "exact"
REGEX = "regex"


class Rule:
    """One parsed rule."""

    __slots__ = ("pattern", "action", "kind", "value", "source", "line")

    def __init__(self, pattern, action, kind, value, source, line):
        self.pattern = pattern
        self.action = action
        self.kind = kind
        self.value = value
        self.source = source
        self.line = line

    def as_dict(self):
        return {
            "pattern": self.pattern,
            "action": self.action,
            "source": self.source,
            "line": self.line,
        }

    def __repr__(self):
        return "<Rule %s %s>" % (self.action, self.pattern)


class RuleSet:
    """A loaded set of rules."""

    def __init__(self, rules=None, sources=None, loaded_at=None):
        self.rules = list(rules or [])
        self.sources = list(sources or [])
        self.loaded_at = loaded_at

    def __len__(self):
        return len(self.rules)

    def __iter__(self):
        return iter(self.rules)

    @property
    def count(self):
        return len(self.rules)

    @property
    def block_count(self):
        return sum(1 for r in self.rules if r.action == BLOCK)

    @property
    def allow_count(self):
        return sum(1 for r in self.rules if r.action == ALLOW)

    def match(self, qname):
        """Return (decision, rule) where decision is 'block', 'allow' or None."""
        name = qname.lower().rstrip(".")
        if not name:
            return None, None
        parents = list(self._parent_domains(name))
        for rule in self.rules:
            if rule.action != ALLOW:
                continue
            if rule.kind == DOMAIN and rule.value in parents:
                return ALLOW, rule
            if rule.kind == EXACT and rule.value == name:
                return ALLOW, rule
            if rule.kind == REGEX and rule.value.search(name):
                return ALLOW, rule
        for rule in self.rules:
            if rule.action != BLOCK:
                continue
            if rule.kind == DOMAIN and rule.value in parents:
                return BLOCK, rule
            if rule.kind == EXACT and rule.value == name:
                return BLOCK, rule
            if rule.kind == REGEX and rule.value.search(name):
                return BLOCK, rule
        return None, None

    @staticmethod
    def _parent_domains(name):
        parts = name.split(".")
        for i in range(len(parts) - 1):
            yield ".".join(parts[i:])

    def as_list(self):
        return [r.as_dict() for r in self.rules]


def parse_rule(line, source=None, number=0):
    """Parse one line into a Rule, or return None for comments and blanks."""
    text = line.strip()
    if not text or text.startswith("!") or text.startswith("#"):
        return None
    action = BLOCK
    if text.startswith("@@"):
        action = ALLOW
        text = text[2:].strip()
        if not text:
            return None
    if text.startswith("/") and text.endswith("/") and len(text) > 1:
        body = text[1:-1]
        try:
            compiled = re.compile(body)
        except re.error:
            return None
        return Rule(text, action, REGEX, compiled, source, number)
    if text.startswith("||"):
        domain = text[2:].split("^")[0].split("$")[0].strip().lower()
        if not domain:
            return None
        return Rule(text, action, DOMAIN, domain, source, number)
    if text.startswith("|"):
        domain = text[1:].split("|")[0].split("^")[0].strip().lower()
        if not domain:
            return None
        return Rule(text, action, EXACT, domain, source, number)
    domain = text.split("^")[0].split("$")[0].split("/")[0].strip().lower()
    if not domain or " " in domain:
        return None
    return Rule(text, action, DOMAIN, domain, source, number)


def load_rule_file(path):
    """Read one rule file and return the rules it contains."""
    rules = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, raw in enumerate(handle, start=1):
            rule = parse_rule(raw, source=os.path.abspath(path), number=number)
            if rule is not None:
                rules.append(rule)
    return rules


def load_rules(paths):
    """Load and merge several rule files into a RuleSet."""
    rules = []
    sources = []
    for path in paths or []:
        expanded = os.path.expanduser(path)
        if not os.path.isfile(expanded):
            raise FileNotFoundError("rule file not found: %s" % expanded)
        rules.extend(load_rule_file(expanded))
        sources.append(os.path.abspath(expanded))
    return RuleSet(rules, sources)

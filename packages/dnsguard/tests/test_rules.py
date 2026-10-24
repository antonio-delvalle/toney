import os
import tempfile
import unittest

from dnsguard import rules


class ParseRuleTests(unittest.TestCase):
    def test_domain_rule(self):
        rule = rules.parse_rule("||ads.example.net^")
        self.assertEqual(rule.action, rules.BLOCK)
        self.assertEqual(rule.kind, rules.DOMAIN)
        self.assertEqual(rule.value, "ads.example.net")

    def test_allow_rule(self):
        rule = rules.parse_rule("@@||cdn.example.net^")
        self.assertEqual(rule.action, rules.ALLOW)
        self.assertEqual(rule.value, "cdn.example.net")

    def test_exact_rule(self):
        rule = rules.parse_rule("|exact.example.net|")
        self.assertEqual(rule.kind, rules.EXACT)
        self.assertEqual(rule.value, "exact.example.net")

    def test_regex_rule(self):
        rule = rules.parse_rule("/^acr[0-9]+\\.example$/")
        self.assertEqual(rule.kind, rules.REGEX)
        self.assertTrue(rule.value.search("acr12.example"))

    def test_comments_are_ignored(self):
        self.assertIsNone(rules.parse_rule("! a comment"))
        self.assertIsNone(rules.parse_rule("# another comment"))
        self.assertIsNone(rules.parse_rule("   "))

    def test_invalid_regex_is_ignored(self):
        self.assertIsNone(rules.parse_rule("/[unclosed/"))

    def test_bare_domain(self):
        rule = rules.parse_rule("bare.example.net")
        self.assertEqual(rule.kind, rules.DOMAIN)
        self.assertEqual(rule.value, "bare.example.net")


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.rules = rules.RuleSet([
            rules.parse_rule("||ads.example.net^"),
            rules.parse_rule("||tracker.example.org^"),
            rules.parse_rule("@@||cdn.example.net^"),
            rules.parse_rule("/^acr[0-9]+\\.example\\.net$/"),
        ])

    def test_blocks_subdomain(self):
        decision, rule = self.rules.match("pixel.ads.example.net")
        self.assertEqual(decision, rules.BLOCK)
        self.assertEqual(rule.value, "ads.example.net")

    def test_blocks_the_domain_itself(self):
        decision, _ = self.rules.match("ads.example.net")
        self.assertEqual(decision, rules.BLOCK)

    def test_allow_wins_over_block(self):
        decision, rule = self.rules.match("cdn.example.net")
        self.assertEqual(decision, rules.ALLOW)
        self.assertEqual(rule.value, "cdn.example.net")

    def test_unrelated_name_is_not_matched(self):
        decision, rule = self.rules.match("www.example.com")
        self.assertIsNone(decision)
        self.assertIsNone(rule)

    def test_regex_match(self):
        decision, _ = self.rules.match("acr42.example.net")
        self.assertEqual(decision, rules.BLOCK)

    def test_trailing_dot_is_ignored(self):
        decision, _ = self.rules.match("ads.example.net.")
        self.assertEqual(decision, rules.BLOCK)

    def test_case_is_ignored(self):
        decision, _ = self.rules.match("ADS.Example.Net")
        self.assertEqual(decision, rules.BLOCK)

    def test_parent_domain_does_not_match_unrelated_subdomain(self):
        decision, _ = self.rules.match("notads.example.net")
        self.assertIsNone(decision)


class LoadRulesTests(unittest.TestCase):
    def test_loads_and_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "list.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("! header\n||ads.example.net^\n@@||cdn.example.net^\n")
            loaded = rules.load_rules([path])
        self.assertEqual(loaded.count, 2)
        self.assertEqual(loaded.block_count, 1)
        self.assertEqual(loaded.allow_count, 1)
        self.assertEqual(len(loaded.sources), 1)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            rules.load_rules(["/nonexistent/list.txt"])


if __name__ == "__main__":
    unittest.main()

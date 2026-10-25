import os
import unittest

from dnsguard import rules

PROFILES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "profiles",
)

BLOCKED = [
    "ad.doubleclick.net",
    "googleads.g.doubleclick.net",
    "ade.googlesyndication.com",
    "pagead2.googlesyndication.com",
    "tpc.googlesyndication.com",
]

KEPT = [
    "www.youtube.com",
    "rr1---sn-0opoxu-hxmrk.googlevideo.com",
    "rr6---sn-0opoxu-hxmke.googlevideo.com",
    "i.ytimg.com",
    "yt3.ggpht.com",
    "www.gstatic.com",
]


class YouTubeAdsProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = rules.load_rules([os.path.join(PROFILES, "youtube-ads.blocklist")])

    def test_blocks_the_ad_hosts_seen_in_the_query_log(self):
        for name in BLOCKED:
            decision, rule = self.rules.match(name)
            self.assertEqual(decision, rules.BLOCK, name)
            self.assertIsNotNone(rule)

    def test_keeps_the_playback_hosts(self):
        for name in KEPT:
            decision, _ = self.rules.match(name)
            self.assertEqual(decision, rules.ALLOW, name)

    def test_playback_hosts_are_not_blocked_by_a_block_rule(self):
        for name in KEPT:
            blocked = [r for r in self.rules.rules
                       if r.action == rules.BLOCK and r.kind == rules.DOMAIN
                       and r.value in rules.RuleSet._parent_domains(name)]
            self.assertEqual(blocked, [], name)

    def test_profile_loads_without_errors(self):
        self.assertGreater(self.rules.block_count, 0)
        self.assertGreater(self.rules.allow_count, 0)


if __name__ == "__main__":
    unittest.main()

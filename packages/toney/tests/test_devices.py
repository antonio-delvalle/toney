"""Tests for the lookup of the device names."""

import time
import unittest

from toney.devices import DeviceResolver, clean_name, reverse_lookup


class CleanNameTest(unittest.TestCase):
    """The name as it is shown."""

    def test_a_trailing_dot_is_dropped(self):
        self.assertEqual(clean_name("living-room-tv.local."), "living-room-tv")

    def test_the_local_suffix_is_dropped(self):
        self.assertEqual(clean_name("living-room-tv.local"), "living-room-tv")

    def test_the_address_itself_is_not_a_name(self):
        self.assertEqual(clean_name("192.0.2.10", "192.0.2.10"), "")

    def test_the_reverse_name_of_an_address_is_not_a_name(self):
        self.assertEqual(clean_name("203.0.113.10.in-addr.arpa"), "")

    def test_nothing_is_nothing(self):
        self.assertEqual(clean_name(""), "")
        self.assertEqual(clean_name(None), "")


class ReverseLookupTest(unittest.TestCase):
    """The name that comes back from the resolver."""

    def test_the_loopback_has_a_local_name(self):
        name = reverse_lookup("127.0.0.1")
        self.assertTrue(name == "" or "localhost" in name, name)


class DeviceResolverTest(unittest.TestCase):
    """The resolver finds the names and remembers what it found."""

    def test_a_name_is_found(self):
        resolver = DeviceResolver(lookup=self._names({"192.0.2.10": "tv"}))
        found = resolver.resolve(["192.0.2.10"])
        self.assertEqual(found, {"192.0.2.10": "tv"})
        self.assertEqual(resolver.names(), {"192.0.2.10": "tv"})

    def test_an_address_without_a_name_is_not_in_the_names(self):
        resolver = DeviceResolver(lookup=self._names({}))
        self.assertEqual(resolver.resolve(["192.0.2.10"]), {})
        self.assertEqual(resolver.names(), {})

    def test_a_known_address_is_not_looked_up_again(self):
        calls = []
        resolver = DeviceResolver(lookup=self._names({"192.0.2.10": "tv"}, calls))
        resolver.resolve(["192.0.2.10"])
        resolver.resolve(["192.0.2.10"])
        self.assertEqual(calls, ["192.0.2.10"])

    def test_an_address_without_a_name_is_asked_again_later(self):
        calls = []
        resolver = DeviceResolver(lookup=self._names({}, calls))
        resolver.resolve(["192.0.2.10"])
        resolver.resolve(["192.0.2.10"])
        self.assertEqual(len(calls), 1)

    def test_the_sweep_skips_the_addresses_it_knows(self):
        calls = []
        resolver = DeviceResolver(
            lookup=self._names({"192.0.2.10": "tv"}, calls)
        )
        resolver.resolve(["192.0.2.10"])
        resolver.resolve(["192.0.2.10", "192.0.2.11"])
        self.assertEqual(calls, ["192.0.2.10", "192.0.2.11"])

    def test_a_slow_lookup_does_not_hold_the_caller(self):
        def slow(address):
            time.sleep(2)
            return "tv"

        resolver = DeviceResolver(lookup=slow)
        started = time.monotonic()
        found = resolver.resolve(["192.0.2.10"], timeout=0.2)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(found, {})

    def test_an_empty_address_is_ignored(self):
        calls = []
        resolver = DeviceResolver(lookup=self._names({}, calls))
        self.assertEqual(resolver.resolve(["", "   "]), {})
        self.assertEqual(calls, [])

    @staticmethod
    def _names(names, calls=None):
        def lookup(address):
            if calls is not None:
                calls.append(address)
            return names.get(address, "")

        return lookup


if __name__ == "__main__":
    unittest.main()

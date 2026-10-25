"""Tests for the formatting helpers of the Toney interface."""

import os
import time
import unittest

import support
from toney.formatting import (
    format_bytes,
    format_duration,
    format_time,
    format_timestamp,
    parse_timestamp,
)

ZONE = "America/Mexico_City"

ZONE_ROOTS = (
    "/usr/share/zoneinfo",
    "/usr/share/lib/zoneinfo",
    "/var/db/timezone/zoneinfo",
    "/etc/zoneinfo",
)


def zone_available(name):
    """Whether the machine knows about a timezone."""
    for root in ZONE_ROOTS:
        if os.path.isfile(os.path.join(root, name)):
            return True
    return False


class LocalTimeTest(unittest.TestCase):
    """Timestamps are written in UTC and shown in the timezone of the machine."""

    def setUp(self):
        if not hasattr(time, "tzset"):
            self.skipTest("this platform cannot switch the timezone")
        if not zone_available(ZONE):
            self.skipTest("the {0} timezone is not installed".format(ZONE))
        self.previous = os.environ.get("TZ")
        os.environ["TZ"] = ZONE
        time.tzset()
        self.addCleanup(self._restore)

    def _restore(self):
        if self.previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.previous
        time.tzset()

    def test_a_timestamp_becomes_a_readable_local_time(self):
        self.assertEqual(
            format_timestamp("2026-10-24T09:02:01Z"),
            "Saturday October 24, 03:02:01",
        )

    def test_the_time_of_day_is_local_too(self):
        self.assertEqual(format_time("2026-10-24T09:02:01Z"), "03:02:01")

    def test_a_timestamp_without_a_zone_is_read_as_utc(self):
        self.assertEqual(
            format_timestamp("2026-10-24T09:02:01"),
            "Saturday October 24, 03:02:01",
        )

    def test_a_timestamp_with_fractions_keeps_its_second(self):
        self.assertEqual(
            format_timestamp("2026-10-24T09:02:01.250000Z"),
            "Saturday October 24, 03:02:01",
        )

    def test_an_offset_timestamp_is_read(self):
        self.assertEqual(
            format_timestamp("2026-10-24T09:02:01+00:00"),
            "Saturday October 24, 03:02:01",
        )

    def test_a_broken_timestamp_is_left_alone(self):
        self.assertEqual(format_timestamp("not a time"), "not a time")

    def test_an_empty_timestamp_is_left_alone(self):
        self.assertEqual(format_timestamp(""), "")


class ParseTimestampTest(unittest.TestCase):
    """The timestamps of the service are read back as instants."""

    def test_a_service_timestamp_is_read(self):
        self.assertEqual(
            parse_timestamp("2026-10-24T09:02:01Z"), 1792832521.0
        )

    def test_a_number_is_a_posix_time(self):
        self.assertEqual(parse_timestamp(1792832521), 1792832521.0)

    def test_nothing_is_nothing(self):
        self.assertIsNone(parse_timestamp(""))
        self.assertIsNone(parse_timestamp(None))

    def test_a_boolean_is_not_a_time(self):
        self.assertIsNone(parse_timestamp(True))


class SizeTest(unittest.TestCase):
    """Byte counts are shown in the unit that fits them."""

    def test_a_small_count_is_in_bytes(self):
        self.assertEqual(format_bytes(512), "512 B")

    def test_a_large_count_is_in_mebibytes(self):
        self.assertEqual(format_bytes(2048), "2.0 KiB")

    def test_a_missing_count_is_a_dash(self):
        self.assertEqual(format_bytes(None), "-")


class DurationTest(unittest.TestCase):
    """Durations are shown in the unit that fits them."""

    def test_seconds_are_shown_as_seconds(self):
        self.assertEqual(format_duration(30), "30s")

    def test_minutes_are_shown_as_minutes(self):
        self.assertEqual(format_duration(125), "2m 5s")

    def test_hours_are_shown_as_hours(self):
        self.assertEqual(format_duration(3700), "1h 1m")

    def test_a_missing_duration_is_a_dash(self):
        self.assertEqual(format_duration(None), "-")


if __name__ == "__main__":
    unittest.main()

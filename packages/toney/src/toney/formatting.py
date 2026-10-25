"""Formatting helpers shared by the Toney views."""

from __future__ import annotations

import datetime
import time
from typing import Optional

TIMESTAMP_FORMAT = "%A %B %d, %H:%M:%S"

_ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def parse_timestamp(value) -> Optional[float]:
    """Read a timestamp written by the service and return a POSIX time.

    The service writes UTC, so a timestamp without a zone is read as UTC.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in _ISO_FORMATS:
        try:
            parsed = datetime.datetime.strptime(text, pattern)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.timestamp()
    return None


def format_timestamp(value) -> str:
    """Render a timestamp in the timezone of this machine."""
    moment = parse_timestamp(value)
    if moment is None:
        return str(value or "")
    return time.strftime(TIMESTAMP_FORMAT, time.localtime(moment))


def format_time(value) -> str:
    """Render a timestamp as the local time of the day."""
    moment = parse_timestamp(value)
    if moment is None:
        return str(value or "")
    return time.strftime("%H:%M:%S", time.localtime(moment))


def format_bytes(value) -> str:
    """Render a byte count in a human readable way."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(number) < 1024.0:
            if unit == "B":
                return "{0:.0f} {1}".format(number, unit)
            return "{0:.1f} {1}".format(number, unit)
        number /= 1024.0
    return "{0:.1f} PiB".format(number)


def format_duration(seconds) -> str:
    """Render a duration in seconds as a compact human readable string."""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "-"
    if total < 0:
        return "-"
    if total < 60:
        return "{0}s".format(total)
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return "{0}m {1}s".format(minutes, secs)
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return "{0}h {1}m".format(hours, minutes)
    days, hours = divmod(hours, 24)
    return "{0}d {1}h {2}m".format(days, hours, minutes)

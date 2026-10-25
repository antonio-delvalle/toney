"""Finding the name of the device behind an address.

The service only ever sees addresses, so the names have to come from
somewhere else.  A reverse lookup is the one source that is both local and
free: the router that handed out the address usually publishes a name for
it, and the system resolver turns that into a hostname.

The lookups are slow when the resolver has nothing to say, so they run in
the background and the caller gives up waiting.  What they found is kept,
and an address that had no name is asked about again later, in case the
router was only slow that once.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Callable, Dict, Iterable, Optional

WORKERS = 4
TIMEOUT = 5.0
MAX_ADDRESSES = 64
RETRY_SECONDS = 300.0


def clean_name(name: str, address: str = "") -> str:
    """The name as it is shown: no trailing dot, no local suffix.

    A resolver that has nothing to say may answer with the address itself or
    with the reverse name of the address, which says nothing either.
    """
    name = str(name or "").strip().rstrip(".")
    if not name or name == address:
        return ""
    if name.endswith(".in-addr.arpa") or name.endswith(".ip6.arpa"):
        return ""
    if name.endswith(".local"):
        name = name[: -len(".local")]
    return name


def reverse_lookup(address: str) -> str:
    """The hostname of an address, or an empty string when it has none."""
    try:
        name = socket.gethostbyaddr(address)[0]
    except OSError:
        return ""
    return clean_name(name, address)


class DeviceResolver:
    """Looks up the names of the devices and remembers what it found."""

    def __init__(self, lookup: Optional[Callable[[str], str]] = None) -> None:
        self.lookup = lookup or reverse_lookup
        self._names: Dict[str, str] = {}
        self._checked: Dict[str, float] = {}
        self._lock = threading.Lock()

    def names(self) -> Dict[str, str]:
        """The names that were found, by address."""
        with self._lock:
            return {a: n for a, n in self._names.items() if n}

    def resolve(
        self, addresses: Iterable[str], timeout: float = TIMEOUT
    ) -> Dict[str, str]:
        """Look up the addresses that are not known yet.

        The lookups run in the background and the call gives up after
        *timeout* seconds.  The ones that answer later still land in the
        cache, so the next sweep finds them.
        """
        pending = []
        now = time.monotonic()
        for address in addresses:
            address = str(address or "").strip()
            if not address:
                continue
            with self._lock:
                checked = self._checked.get(address)
            if checked is None or now - checked >= RETRY_SECONDS:
                pending.append(address)
        pending = pending[:MAX_ADDRESSES]
        if not pending:
            return {}
        found: Dict[str, str] = {}
        lock = threading.Lock()
        queue = list(pending)

        def worker() -> None:
            while True:
                with lock:
                    if not queue:
                        return
                    address = queue.pop(0)
                name = self.lookup(address)
                with self._lock:
                    self._names[address] = name
                    self._checked[address] = time.monotonic()
                if name:
                    with lock:
                        found[address] = name

        threads = [
            threading.Thread(target=worker, daemon=True)
            for _ in range(min(WORKERS, len(pending)))
        ]
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + timeout
        for thread in threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        return found

# Investigation archive

The measurements and reverse engineering that Toney was built on. They are
kept here because a filtering tool that nobody can check is just a belief.

Everything in this folder was **measured or executed against real devices**,
not inferred from documentation. Where something did not work, the failure is
recorded as carefully as the success — the dead ends are the expensive part
of the work, and they are what stop the next person from repeating them.

| Document | What it holds |
|---|---|
| [tv-recon.md](tv-recon.md) | The smart TV's control surface: REST, WebSocket, UPnP, the pairing flow, the app inventory, the power state machine, and what this firmware refuses to do. |
| [router-admin-api.md](router-admin-api.md) | The GPON router's proprietary admin API: session token, password hashing, the AES config-write format, the field id map, and the limits of its DNS-block feature. |
| [telemetry-strategy.md](telemetry-strategy.md) | The whole strategy: what the telemetry is, which hosts carry it, how the filter was built, what is deployed, the per-app measured inventory, the leak check, and why a DNS filter cannot be Brave. |
| [device-privacy-checklist.md](device-privacy-checklist.md) | The half the DNS layer cannot do: account, privacy switches, voice assistant, log upload. |
| [artifacts.md](artifacts.md) | The catalogue of everything that was built, what it proved, and the rule engine semantics. |

## How the work was done

1. **Inventory first.** Identify the devices on the network, the ports they
   expose, and which ones answer. The neighbour table is polled until it
   stops changing; the first stable table is the real one.
2. **Establish a closed loop before anything else.** A write that cannot be
   read back is not a capability. The remote key injection was verified by
   reading the resulting state over a completely different protocol (UPnP),
   not by the same channel that wrote it.
3. **Find the measurement surface before changing anything.** The router's
   NAT session table turned out to be the instrument that made every later
   question answerable — including the question of whether the filter was
   doing anything at all.
4. **Read the vendor's own code.** The router's cipher was not
   re-implemented; it was lifted out of the page the router itself serves and
   evaluated. The same trick applies to the config format: the numeric ids
   come from the page's own `addCfg()` calls.
5. **Measure the telemetry, do not guess it.** Each application was launched
   and the query log harvested. The hosts that appeared were classified as
   telemetry or function, and only the first kind was blocked.
6. **Prove the negative.** For every blocked host, the leak check resolves it
   and intersects the result with the device's live connections. Zero overlap
   is the only acceptable answer.

## The three findings that shaped the design

**The device does not use the router's resolver.** It took its DNS from DHCP
and kept a hardcoded public resolver as a fallback, so anything configured on
the router was invisible to it. The fix was to make the filtering host the
resolver the device is actually given.

**A router cannot be chained to a local resolver.** Pointing the router's
own upstream at a LAN-hosted resolver produced no queries at all and took
the router's DNS down. The filtering service has to be the resolver the
device talks to, directly.

**A DNS filter is not an ad blocker.** It sees hostnames, never payloads.
Blocking ad *hosts* is reachable; stripping ad *slots* out of a video
player is not. See [telemetry-strategy.md](telemetry-strategy.md) §13 for the
full argument and the alternatives that were rejected.

## Sanitisation

Every address, serial, MAC, token and identifier in this archive has been
replaced with a documentation-range value (`192.0.2.0/24`, `198.51.100.0/24`,
`00:11:22:33:44:55`) or a placeholder. The findings, the numbers and the
conclusions are unchanged. The repository enforces this with a check that
runs in CI, so the archive cannot quietly start leaking again.

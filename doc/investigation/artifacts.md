# Investigation — the artefact catalogue

> Part of the [Toney](../README.md) investigation archive. Every address,
> serial, MAC and identifier in this document has been replaced with a
> documentation-range value; the technical findings are unchanged.

Everything that was built to answer the questions lives here: what it was
for, what it proved, and what it should not be used for again.

The scripts themselves were kept in the working directory that still runs the
filter; this document is the catalogue, because the scripts are mechanical and
the knowledge in them is the part worth keeping.

## The filter

| Artefact | Purpose |
|---|---|
| `dnsfilter.py` | the DNS filter: UDP/TCP listener, rule engine, query log. The prototype of `dnsguard`. |
| `run_dnsfilter.sh` | wraps the filter in `caffeinate -i -m` so the host does not sleep while it runs (no root needed). |
| `com.local.samsung-tv-dnsfilter.plist` | launchd unit: `RunAtLoad` + `KeepAlive`, so the filter restarts if it dies. |
| `tv-dns.log` | the live query log: one JSON object per query. |

```json
{"client": "192.0.2.64", "name": "unagi-na.amazon.com.", "type": "A", "decision": "BLOCK", "rule": "||unagi-na.amazon.com^"}
```

The log is the instrument that turned a guess into a measurement. Everything
in the profile shipped in `profiles/` was either observed in it or verified
against it.

### Rule engine semantics

The engine the filter uses, and the one `dnsguard` reimplements:

- `||domain^` blocks the domain **and every subdomain**. Matching walks the
  parent domains of the queried name, from the full name down to the second
  label, and stops before the bare TLD.
- `@@||domain^` is a KEEP exception. **KEEP rules are evaluated first and
  always win**, which is what makes a narrow block list safe.
- `/regex/` matches against the whole name; an invalid regular expression is
  skipped rather than fatal.
- Comments start with `!` or `#`.

Two details that are easy to get wrong and were measured rather than assumed:

1. The **full name** is part of the parent chain, so `||example.com^` blocks
   `example.com` itself as well as `ads.example.com`.
2. The **bare TLD is not**, so `||example.com^` does not block `com`.

## The router client

| Artefact | Purpose |
|---|---|
| `telmex_cgi.js` | login, session, and the `apply_abstract.cgi` writer (DCBA + AES). The reference implementation — see [router-admin-api.md](router-admin-api.md). |
| `telmex_login.py` | the same login flow in Python. |
| `router_session.js` | holds a session open and fetches token-gated paths. |
| `router_conf.js` | read or write **any** config page by logical name; maps the logical name to the numeric id. |
| `router_dns_rules.js` | `show` / `deploy` / `verify` / `rollback` for the router's 10 native DNS blocks. |
| `router_fwurl.js` | the URL-blocking list. Kept as evidence that URL blocking is not a DNS filter. |
| `ubus_client.py` | a LuCI/ubus JSON-RPC client. **Does not work on this firmware** — `/ubus` returns an HTML page. Kept so nobody repeats the attempt. |
| `deploy_openwrt.sh` | the SSH route: installs the rule list as a dnsmasq include and can roll it back. This is the ancestor of the router driver in `dnsguard`. |

## The measurement tools

| Artefact | Purpose |
|---|---|
| `tv_conns.js` | dumps the TV's live connections from the router's NAT table and classifies them. |
| `tv_nat_ips.js` | the same, reduced to the endpoint list. |
| `leak_check.py` | resolves every host the filter blocked for the device, intersects those IPs with the device's live NAT endpoints, and reports any overlap. |
| `tv_netinfo.py` | asks the TV for its own network configuration over the device WebSocket API. |
| `tvctl.py` | the device control tool: discovery, REST, UPnP, WebSocket. |
| `watch_tv.py` | waits for the device to appear on the LAN and identifies it by OUI. |
| `watch_sdb.py` | waits for the SDB developer port to open. |
| `apps_installed.json` | the app inventory snapshot. |
| `tv_token.txt` | the pairing token for the remote channel. |

### How the leak check works, and why it is the right question

Blocking a name is only half of it. The other half is whether the device
still reached the address behind that name. The leak check therefore:

1. collects the names the filter blocked for that client,
2. resolves each of them to its current IPs,
3. intersects those IPs with the device's live NAT endpoints.

Zero overlap means the device asked and never arrived. It is the only
assertion in the whole investigation that proves the filter actually stops
traffic rather than just returning a different answer.

## Blocklist provenance

The profile in `profiles/samsung-tv-telemetry.blocklist` is the merged,
curated result of three sources cross-checked against each other and then
re-measured on a real device:

- a community smart-TV blocklist, per-host, evidence based,
- a Pi-hole blocklist's vendor section,
- a vendor blocklist published for the same platform.

The curation is the work: **70 block rules, 33 KEEP rules.** Every host that
serves firmware, time sync, DRM licensing, the app store, account sign-in,
TV Plus streaming or playback is allowed on purpose. The measurement passes
added the rest — the streaming, crash-reporting and device-telemetry hosts
that only show up once the apps are actually running.

## The device-side checklist

[device-privacy-checklist.md](device-privacy-checklist.md) covers the half
that DNS cannot do: the account, the privacy switches, the voice assistant
and the log upload. It exists because the DNS layer cannot stop audio from
leaving the house, and a filter that people trust to be complete is worse
than one that is honest about its edge.

## What is deliberately not here

- No credentials, tokens, serials or device identifiers.
- No captured traffic dumps.
- No unmodified vendor firmware or binaries.

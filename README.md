# Toney

Two small applications for running a DNS filter on a network you control:

- **`dnsguard`** — the filtering service. It answers DNS queries, blocks the
  names you tell it to block, and writes a query log that expires on its own.
- **`toney`** — the terminal UI. It manages the service completely: start it,
  stop it, watch what it is doing, change the rules, change the settings.

They are separate applications on purpose. The service runs on its own, with
no user interface and no dependency on the TUI; the TUI is a client that
talks to the service over a Unix socket and nothing else.

No dependencies beyond the Python standard library. No accounts, no cloud, no
telemetry of its own.

## Why

A smart TV or a set-top box talks to a lot of infrastructure that has nothing
to do with playing a video: viewing-history fingerprinting, advertising
measurement, crash reporting, quality-of-experience probes. Some of it is
easy to switch off in the device's own settings, and some of it is not.

A DNS filter sits between the device and the network and answers for names
the device should not be reaching. It cannot see inside encrypted traffic and
it does not need to: blocking a name is enough to stop the conversation from
starting.

Two rules keep this honest:

1. **A filter that breaks the device is not a privacy tool.** Every profile
   ships with explicit KEEP rules for the hosts that make the device work.
2. **Measure, do not guess.** The query log is the instrument. Block what you
   actually saw, keep what you need.

## Install

```bash
git clone https://github.com/antonio-delvalle/toney.git
cd toney
python3 -m pip install -e packages/dnsguard
python3 -m pip install -e packages/toney
```

Python 3.10 or newer. Nothing else is needed.

## Run

Start the service with a profile:

```bash
dnsguard serve \
  --listen 0.0.0.0:5353 \
  --upstream 192.0.2.53 \
  --rules profiles/samsung-tv-telemetry.blocklist
```

Then point your devices at `192.0.2.53:5353` as their DNS server — or run it
on the router itself, which is usually the better place.

Open the interface:

```bash
toney
```

The TUI shows what the service is doing, lets you start and stop it, browse
the log, search the rules and change the configuration.

It also edits the rule set from the keyboard: `a` blocks a domain, `k` adds a
KEEP exception, `d` removes the selected rule, and the change is applied to
the running service immediately.

And it can push the rule set to a router that runs dnsmasq, so the filter
keeps working when the machine running the service is off. The router is
always the coarser of the two: dnsmasq cannot express a KEEP exception or a
regular expression, so it is a second layer, never a replacement.

## How the two fit together

```
        devices on the network
                |
                | DNS :53
                v
        +--------------------+
        |     dnsguard       |   blocks names, forwards the rest
        |  (the service)     |   writes a JSONL query log
        +--------------------+
                |
                | Unix socket, newline-delimited JSON
                v
        +--------------------+
        |      toney        |   the terminal UI
        |  (the interface)  |   manages the service
        +--------------------+
```

The protocol is documented in [`doc/CONTROL_PROTOCOL.md`](doc/CONTROL_PROTOCOL.md).

## Logs expire

The query log is written to one file per day and deleted when it falls out
of the retention window (5 days by default). A file that grows past the size
cap is compressed and rolled over, so the log cannot grow without bound. The
window is configurable.

## Documentation

| Document | What it covers |
|---|---|
| [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md) | how the pieces fit, and why they are split this way |
| [`doc/CONTROL_PROTOCOL.md`](doc/CONTROL_PROTOCOL.md) | the socket protocol between the two applications |
| [`doc/investigation/`](doc/investigation/) | the measurements and reverse engineering Toney was built on |
| [`profiles/README.md`](profiles/README.md) | rule syntax and the bundled profiles |

## Licence

MIT. See [`LICENSE`](LICENSE).

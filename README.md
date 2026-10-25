# Toney

Two small applications for running a DNS filter on a network you control:

- **`dnsguard`** — the filtering service. It answers DNS queries, blocks the
  names you tell it to block, and writes a query log that expires on its own.
- **`toney`** — the terminal UI. It manages the service completely: start it,
  stop it, watch what it is doing, change the rules, change the settings.

They are separate applications on purpose. The service runs on its own, with
no user interface and no dependency on the TUI; the TUI is a client that
talks to the service over a Unix socket and nothing else.

The service needs nothing but the Python standard library. The interface is
built with [Textual](https://textual.textualize.io), the only third-party
package in the project. No accounts, no cloud, no telemetry of its own.

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
python3 -m venv ~/.venvs/toney
~/.venvs/toney/bin/python -m pip install -e packages/dnsguard
~/.venvs/toney/bin/python -m pip install -e packages/toney
```

Python 3.10 or newer. The virtual environment is not required, but it keeps the
console scripts and the interpreter that can import them together, which
matters once the TUI starts the service as a child process.

## Run

Start the service with a profile:

```bash
dnsguard serve \
  --listen 0.0.0.0:5353 \
  --upstream 192.0.2.53 \
  --rules profiles/samsung-tv-telemetry.blocklist
```

A device can only be told to use port 53 — DHCP hands out an address, and the
port is implicit. So for real hardware, either run the service on `:53`
directly, or put dnsmasq in front of it on 53 and let it forward to the
service's high port.

Open the interface:

```bash
toney
```

The TUI shows what the service is doing, lets you start and stop it, browse
the log, search the rules and change the configuration.

It also edits the rule set from the keyboard: `a` blocks a domain, `k` adds a
KEEP exception, `d` removes the selected rule, and the change is applied to
the running service immediately and written to the configuration, so it
survives a restart.

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

The protocol is one JSON object per line in each direction over that socket.

## Logs expire

The query log is written to one file per day and deleted when it falls out
of the retention window (5 days by default). A file that grows past the size
cap is compressed and rolled over, so the log cannot grow without bound. The
window is configurable.

## Documentation

| Document | What it covers |
|---|---|
| [`packages/dnsguard/README.md`](packages/dnsguard/README.md) | the filtering service: configuration, rule matching, the query log, the control socket and router deployment |
| [`packages/toney/README.md`](packages/toney/README.md) | the terminal UI: configuration, the views and their key bindings |
| [`profiles/README.md`](profiles/README.md) | rule syntax and the bundled profiles |

## Licence

MIT. See [`LICENSE`](LICENSE).

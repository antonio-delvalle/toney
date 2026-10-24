# Running Toney

How to install, configure and run the two applications, and how to check that
the filtering actually works. Every command here was executed and verified
before being written down.

## What you are running

Toney is two programs that talk to each other over a Unix socket.

```
  toney  (terminal UI)  ──JSON lines over a Unix socket──▶  dnsguard  (service)
      curses TUI                                              UDP+TCP DNS on :5353
      5 views, rule editor                                   query log, rule matching
      start/stop/restart                                     upstream forwarding
```

- **`dnsguard`** does the filtering. It is headless, has no user interface and
  never talks to the TUI directly. It can run on a machine with no terminal.
- **`toney`** is a curses TUI. It is a pure socket client: it does not touch
  the service's files, ports or processes, except to start and stop them.

`dnsguard` alone is enough to filter DNS. The TUI adds the dashboard, the
query log browser, the rule editor and the router deploy.

## Prerequisites

- Python **3.10 or newer** (both packages declare `requires-python = ">=3.10"`)
- **No third-party packages.** Everything is standard library only, and CI
  enforces it with `scripts/check_stdlib_only.py`.
- A working `curses`. Only the TUI needs it; the service does not.

### Check curses before you start

```bash
python3 -c "import curses; print('curses ok')"
```

If that fails with a `dlopen` error mentioning `libncursesw`, the interpreter
was built against an ncurses that is no longer installed — a common outcome
when Homebrew's `ncurses` is upgraded or removed under a pyenv build. Nothing
in Toney is wrong; the interpreter is.

The service still works under a broken-curses Python, so you can get filtering
running first and sort the TUI out after.

```bash
# find an interpreter that can import curses
for p in /opt/homebrew/bin/python3.1* /usr/local/bin/python3.1* /usr/bin/python3; do
  [ -x "$p" ] && echo "$p -> $($p --version 2>&1) curses:$($p -c 'import curses; print("ok")' 2>&1 | tail -1)"
done
```

Pick one that reports `curses:ok` **and** is 3.10 or newer.

## Install

Use a virtual environment so the console scripts and their imports are
consistent no matter which directory you launch from.

```bash
cd /path/to/toney
python3 -m venv ~/.venvs/toney
~/.venvs/toney/bin/python -m pip install --upgrade pip
~/.venvs/toney/bin/python -m pip install -e packages/dnsguard -e packages/toney
```

That gives you two console scripts, `dnsguard` and `toney`.

Editable installs matter more than usual here: the TUI's supervisor spawns the
service as a child process, and the child has to be able to `import dnsguard`
regardless of its working directory.

## Configure

**There are two configuration files, and they belong to different programs.**
This is the single most common source of confusion.

| File | Read by | Purpose |
|---|---|---|
| `~/.config/toney/dnsguard.json` | `dnsguard` | how the service filters, listens and logs |
| `~/.config/toney/toney.json` | `toney` | where the socket is, and how to launch the service |

### `~/.config/toney/dnsguard.json`

This is the service's default config path, so `dnsguard serve` picks it up with
no flags at all.

```json
{
  "listen": "127.0.0.1:5354",
  "upstream": ["<your-isp-dns-ip>"],
  "rules": ["/path/to/toney/profiles/samsung-tv-telemetry.blocklist"],
  "log_dir": "~/.local/state/toney/dnsguard",
  "control": "~/.local/state/toney/dnsguard.sock",
  "retention_days": 5
}
```

If you leave `upstream` out, the service reads the system resolvers from
`/etc/resolv.conf`. Set it explicitly if you want the TV's traffic to leave
through the same resolver the rest of the house uses.

Paths are expanded with `~`. Relative paths are resolved against the working
directory of the process, so absolute paths are safer in the config.

### `~/.config/toney/toney.json`

```json
{
  "control_socket": "~/.local/state/toney/dnsguard.sock",
  "service": {
    "command": ["/absolute/path/to/.venvs/toney/bin/dnsguard", "serve"],
    "cwd": null,
    "env": {}
  },
  "rules_file": "~/.config/toney/rules.blocklist"
}
```

Use the **absolute path** to the virtualenv's `dnsguard` script. There is no
shell to expand `~` in `command`, and the `python3` on your `PATH` may not be
the interpreter that has `dnsguard` installed.

`control_socket` must match the service's `control` setting, or the TUI will
report the service as unreachable.

### Why the config file and not command-line flags

If you start the service with flags:

```bash
dnsguard serve --listen 127.0.0.1:5354 --rules ./my.blocklist
```

and then press `r` to restart it from inside the TUI, the supervisor restarts it
with the **default command** from `toney.json` — silently discarding your flags.

Settings in `~/.config/toney/dnsguard.json` survive a restart, because
`dnsguard serve` with no `--config` reads that file.

## Run

Two terminals:

```bash
# Terminal 1 - the service
~/.venvs/toney/bin/dnsguard serve
```

```
dnsguard 0.1.0 listening on 127.0.0.1:5354
dnsguard control socket: ~/.local/state/toney/dnsguard.sock
dnsguard rules loaded: 103 from 1 file(s)
```

```bash
# Terminal 2 - the TUI
~/.venvs/toney/bin/toney
```

Or skip the first terminal entirely: run `toney` and press **`s`** to start the
service. The supervisor starts the process, waits for the socket to appear and
reports the service as running.

## Verify that it filters

Point a query at the listener. A blocked name must come back NXDOMAIN, and a
name covered by a KEEP rule must be forwarded and answer normally.

```bash
dig @127.0.0.1 -p 5354 samsungacr.com
# -> status: NXDOMAIN

dig @127.0.0.1 -p 5354 acr0.samsungcloudsolution.com
# -> status: NXDOMAIN   (subdomains of a blocked domain)

dig @127.0.0.1 -p 5354 samsungcloudsolution.com
# -> status: NOERROR    (KEEP'd, forwarded upstream)
```

Other checks:

```bash
toney --check              # one line + exit 0/1, suitable for scripts
dnsguard config            # the effective configuration
dnsguard rules             # the rules the service actually loaded
dnsguard logs --limit 20   # recent queries from the service's own log
```

`dnsguard config` and `dnsguard rules` read the same files the service does, so
they are the quickest way to check what the service is *about to* do without
starting the TUI.

The query log records the decision for every request:

```json
{"client":"127.0.0.1","decision":"block","name":"samsungacr.com.","rule":"||samsungacr.com^","ts":"...","type":"A"}
{"client":"127.0.0.1","decision":"allow","name":"samsungcloudsolution.com.","rule":null,"ts":"...","type":"A"}
```

`decision` is one of `allow`, `block`, `cache` or `error`.

## Pointing a real device at it

**Ordinary devices can only use port 53.** DHCP hands out a resolver *address*;
the port is implicitly 53. There is no way to tell a TV "use 192.0.2.10 port
5354" — not through DHCP, not through the network settings menu. A DNS filter
listening on a high port is only reachable by software that lets you choose the
port.

So for real hardware, pick one of:

- **Run `dnsguard` directly on port 53.** Ports below 1024 normally need root,
  but check before assuming — on macOS a non-root process can sometimes bind
  `:53` depending on what else holds it. Binding port 53 while
  `mDNSResponder` is running may fail with `Address already in use`.
- **Front it with dnsmasq.** dnsmasq listens on 53 and forwards to
  `dnsguard` on a high port. This is the better long-term shape and it is the
  one `dnsguard`'s `router.deploy` targets.

Note also that **5353 is the mDNS port**. It is a poor default for a DNS
filter: browsers and devices use it for discovery, and something on the machine
may already hold it.

### A caution about uptime

If the filtering machine goes to sleep or is powered off, a device that depends
on it for DNS will lose resolution entirely — unless it has a fallback
resolver of its own. Some smart TVs keep a hardcoded public resolver as a
second choice, and fall back to it when the configured one stops answering. If
the target device has no such fallback, keep the machine awake
(`caffeinate -i -m`) or plan for an outage.

The same argument applies in reverse: a filter that breaks the device is not a
privacy tool, it is an outage. Every shipped profile ships explicit KEEP rules
for that reason.

## Keys in the TUI

| Key | Action |
|---|---|
| `1`–`5` | dashboard, logs, rules, service, router |
| `s` / `S` / `r` | start / stop / restart the service |
| `R` | reload the rule files |
| `/` | search the current view |
| `c` | config editor |
| `a` | block a domain (adds a rule) |
| `k` | add a KEEP exception |
| `d` | delete a rule |
| `?` | help overlay |
| `q` | quit |

In the rules view, `a` / `k` / `d` rewrite the rule set through `rules.set`, so
changes reach the running service immediately and survive a restart.

## Where things live

| What | Default path |
|---|---|
| Service config | `~/.config/toney/dnsguard.json` |
| TUI config | `~/.config/toney/toney.json` |
| Control socket | `~/.local/state/toney/dnsguard.sock` |
| Query log | `~/.local/state/toney/dnsguard/<date>.jsonl` |
| Rule file (TUI editor) | `~/.config/toney/rules.blocklist` |
| Bundled profiles | `profiles/*.blocklist` in the repository |

## Troubleshooting

**`the curses module is not available in this Python installation`**
Your interpreter cannot import `curses`. See the prerequisite check above. The
service is unaffected.

**`control socket not found` / `service not reachable`**
The socket path in `toney.json` and the `control` setting in
`dnsguard.json` disagree, or the service is not running. Compare them, then
`ls` the socket path.

**`Address already in use` on the listen port**
Something else holds that port. `lsof -nP -i :5353` shows what. Port 5353 in
particular is usually mDNS.

**`No module named dnsguard` when the TUI starts the service**
The child process cannot import the package. Use the absolute path to the
virtualenv's `dnsguard` script in `toney.json` rather than a bare `python3 -m
dnsguard`, and check the `cwd` setting.

**The TUI restarted the service and lost my settings**
Expected. See "Why the config file and not command-line flags" above.

**A name you expect to be blocked is not**
Check the decision in the query log — it may have matched a KEEP rule, or a
different rule than you expected. `toney`'s rules view shows the pattern that
matched.

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

Find an interpreter that can import curses **and** is 3.10 or newer. Check the
interpreters you actually have rather than only the usual system paths — a
pyenv install lives in `~/.pyenv/versions/`:

```bash
for p in ~/.pyenv/versions/*/bin/python3 /opt/homebrew/bin/python3.1* \
         /usr/local/bin/python3.1* /usr/bin/python3; do
  [ -x "$p" ] && echo "$p -> $($p --version 2>&1) curses:$($p -c 'import curses; print("ok")' 2>&1 | tail -1)"
done
```

Pick one that reports `curses:ok` **and** is 3.10 or newer, and build the
virtual environment with that interpreter — not with whatever `python3` happens
to be first on `PATH`.

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

Check that the environment you installed into is the one you are going to run:

```bash
~/.venvs/toney/bin/python --version
~/.venvs/toney/bin/python -c "import curses, dnsguard, toney; print('curses ok')"
```

Editable installs matter more than usual here: the TUI's supervisor spawns the
service as a child process, and the child has to be able to `import dnsguard`
regardless of its working directory.

### Putting the commands on your PATH

The console scripts live in the virtual environment, so on a fresh shell they
are `~/.venvs/toney/bin/toney` and `~/.venvs/toney/bin/dnsguard`. To be able
to type `toney` instead, link them into a directory that is already on your
PATH:

```bash
mkdir -p ~/.local/bin
ln -sf ~/.venvs/toney/bin/toney   ~/.local/bin/toney
ln -sf ~/.venvs/toney/bin/dnsguard ~/.local/bin/dnsguard
```

`~/.local/bin` is on the PATH of most macOS shells already; check with
`echo $PATH`. If it is not there, add it to `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Link the two commands rather than adding the virtual environment's `bin`
directory to the PATH: that directory also holds `python`, `python3` and
`pip`, and putting it on the PATH would make the virtual environment's
interpreter the one every command in every shell uses.

The links point at the interpreter inside the virtual environment, so they
keep working whatever the PATH says — the shebang in the script is absolute.

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
  "rules_file": "~/.config/toney/rules.blocklist",
  "stop_on_exit": true
}
```

Use the **absolute path** to the virtualenv's `dnsguard` script. There is no
shell to expand `~` in `command`, and the `python3` on your `PATH` may not be
the interpreter that has `dnsguard` installed.

`control_socket` must match the service's `control` setting, or the TUI will
report the service as unreachable.

The service is started with `--config <config_path>` appended to `command`,
unless the command already carries a `--config` of its own. `config_path`
defaults to `~/.config/toney/dnsguard.json` — the same file the service reads
on its own — so the two agree on where the settings live by default.

### Why the config file and not command-line flags

If you start the service with flags:

```bash
dnsguard serve --listen 127.0.0.1:5354 --rules ./my.blocklist
```

and then press `r` to restart it from inside the TUI, the supervisor restarts it
with the **default command** from `toney.json` — silently discarding your flags.

Settings in `~/.config/toney/dnsguard.json` survive a restart, because
`dnsguard serve` with no `--config` reads that file.

Changes the TUI makes over the socket are written back to that file, so they
survive a restart too: `a`, `k` and `d` in the rules view rewrite the rule set
and record the new rule file in the configuration, and the configuration editor
(`c`) records the settings it changes. The file is the single source of truth
for what the service does on the next start.

### `stop_on_exit`

Whether quitting the TUI stops a service the TUI started. Leave it `true`
when the TUI is the only thing that runs the service. Set it to `false` when
the service has to outlive the TUI — a launch agent or any other supervisor
that keeps it running (see below).

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

### Letting the operating system own the service

A service the TUI started is stopped when the TUI quits, and it is gone after a
reboot. When a device depends on the filter, it has to keep running when
nobody is looking at the TUI — so hand the process to a system supervisor and
let the TUI ask that supervisor to act.

On macOS that is a launch agent. `~/Library/LaunchAgents/com.local.toney-dnsguard.plist`:

```xml
<dict>
	<key>Label</key>
	<string>com.local.toney-dnsguard</string>
	<key>ProgramArguments</key>
	<array>
		<string>/usr/bin/caffeinate</string>
		<string>-i</string>
		<string>-m</string>
		<string>/absolute/path/to/.venvs/toney/bin/dnsguard</string>
		<string>serve</string>
		<string>--config</string>
		<string>/absolute/path/to/.config/toney/dnsguard.json</string>
	</array>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<dict>
		<key>SuccessfulExit</key>
		<false/>
	</dict>
	<key>ThrottleInterval</key>
	<integer>10</integer>
</dict>
```

`KeepAlive` with `SuccessfulExit` false means the agent restarts the service
when it crashes but leaves it stopped when it was shut down cleanly — a
deliberate stop stays stopped. `caffeinate` keeps the machine awake; drop it
if the machine is a server that never sleeps.

Tell the TUI that the service is managed elsewhere, and how to reach the
manager. In `~/.config/toney/toney.json`:

```json
{
  "control_socket": "~/.local/state/toney/dnsguard.sock",
  "service": {
    "command": ["/absolute/path/to/.venvs/toney/bin/dnsguard", "serve"],
    "cwd": null,
    "env": {},
    "manager": {
      "start": ["launchctl", "kickstart", "gui/501/com.local.toney-dnsguard"],
      "restart": ["launchctl", "kickstart", "-k", "gui/501/com.local.toney-dnsguard"]
    }
  },
  "rules_file": "~/.config/toney/rules.blocklist",
  "stop_on_exit": false
}
```

With `manager` set, `s` and `r` in the TUI run those commands instead of
starting a second copy of the service. `S` still stops the service over the
control socket. Without `manager`, the TUI starts and stops the service itself.

Load the agent and check it:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.toney-dnsguard.plist
launchctl print gui/$(id -u)/com.local.toney-dnsguard | grep -E 'state|pid'
```

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

Use the port the service actually listens on — `5354` above, `53` when the
service owns the DNS port.

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

To check that a change made in the TUI really survives a restart, make it,
restart the service and read the rules again:

```bash
toney            # add a rule with 'a', then press 'r'
dnsguard rules | tail -1     # the count has to be the new one
```

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

Whichever way the filter reaches port 53, it has to be the *same* service the
TUI controls, or the filtering is not under the TUI's control: the TUI would
be showing one rule set while the device is filtered by another. Check it:

```bash
lsof -nP -i :53                     # one process holds the port
toney --check                       # the TUI reaches that service
dnsguard rules | tail -1            # the rules it actually loaded
```

If something else holds port 53 — a previous prototype, another filter — stop
it before starting `dnsguard`. Two processes cannot share the port: the second
one fails with `Address already in use` and says so in its log.

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

`d` deletes the rule that is highlighted in the list you are looking at. With a
search active that is the matching rule, not the rule at the same position in
the full list.

## Where things live

| What | Default path |
|---|---|
| Service config | `~/.config/toney/dnsguard.json` |
| TUI config | `~/.config/toney/toney.json` |
| Control socket | `~/.local/state/toney/dnsguard.sock` |
| Query log | `~/.local/state/toney/dnsguard/<date>.jsonl` |
| Active rule file | `~/.local/state/toney/dnsguard/rules.blocklist` |
| Rule file (TUI editor) | `~/.config/toney/rules.blocklist` |
| Bundled profiles | `profiles/*.blocklist` in the repository |

The rule file the TUI edits and the rule file the service loads are two
copies of the same thing: the TUI writes its file, `rules.set` copies it into
the service's own directory, and the configuration records the copy as the
active one.

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
Expected for settings that were passed as command-line flags: the supervisor
restarts the service with the command from `toney.json`. See "Why the config
file and not command-line flags" above. Settings that live in
`~/.config/toney/dnsguard.json` — including the ones the TUI itself changed —
do survive the restart.

**The service is running but the TUI says it is stopped**
The control socket paths disagree. `control_socket` in `toney.json` and
`control` in `dnsguard.json` have to be the same path.

**The TUI starts a second copy of the service**
The service is already running but on another socket, or it is managed by a
launch agent and the TUI has no `manager` section for it. Two copies cannot
share port 53: the second one fails to bind. Point the TUI at the running
service, or tell it how to reach the manager.

**A name you expect to be blocked is not**
Check the decision in the query log — it may have matched a KEEP rule, or a
different rule than you expected. `toney`'s rules view shows the pattern that
matched.

**The rules view shows a different rule set than the service is using**
The TUI's rule file is `~/.config/toney/rules.blocklist` and the service's is
`~/.local/state/toney/dnsguard/rules.blocklist`. `dnsguard rules` shows what
the service loaded; `dnsguard config` shows which file that is.

# Toney

Toney is a terminal UI that manages the **dnsguard** DNS filtering service.
The service is a separate program; Toney only ever talks to it through the
Unix domain socket control protocol: one JSON object per line in each
direction.
Toney needs Python 3.10 or newer and [Textual](https://textual.textualize.io)
for the interface. The service itself still needs nothing but the standard
library.

## Run

```sh
PYTHONPATH=src python3 -m toney
```

Check that the service answers and exit with 0 or 1, which is handy in CI:

```sh
PYTHONPATH=src python3 -m toney --check
```

Options:

| Option | Meaning |
| --- | --- |
| `--check` | probe the control socket, print one line and exit 0 or 1 |
| `--config PATH` | use a different Toney configuration file |
| `--control PATH` | use a different control socket |

## Configuration

The TUI keeps its own JSON file, by default `~/.config/toney/toney.json`:

```json
{
  "control_socket": "~/.local/state/toney/dnsguard.sock",
  "service": {"command": ["python3", "-m", "dnsguard", "serve"], "cwd": null, "env": {}},
  "config_path": "/etc/toney/dnsguard.json",
  "rules_file": "~/.config/toney/rules.blocklist",
  "clients": {"192.0.2.10": "living-room-tv"}
}
```

A missing or unreadable file is not an error, the defaults above are used.

`rules_file` is where the rules editor writes. The editor rebuilds the rule
set from the rules the service reports, writes it to that path and hands the
path to the service with `rules.set`, so the change survives a restart.

`clients` maps a client address to the name of the device behind it. The name
is shown next to the address in the clients table and in the log tables. An
address that is not in the map is shown on its own.

The map is not the only way a name turns up. Pressing `d` — or starting,
reloading or restarting the service — asks the service for the addresses in
the query log and looks each one up in reverse, which is where the router's
DHCP lease names come from. The names that are found are shown next to the
addresses; the ones in the configuration win over them. They are not written
to the file: a name that the lookup did not find is asked about again five
minutes later, in case the router was only slow that once.

## Views and keys

The views are the dashboard, the logs, the rules, the service screen and the
router. `Tab` switches between them, `1` to `5` jump straight to one of them.
The tab strip at the top works with the mouse as well.

The dashboard is three sections stacked on top of each other: the service,
counters, rules and logs panels side by side, then the clients, then the most
recent log records, which take the rest of the screen.

The log tables show the time in the timezone of the machine, the device name
and the address of the client, the name that was asked for, the decision and
the rule that decided it. The decision is coloured: green for what was
allowed or came from the cache, red for what was blocked.

| Key | Action |
| --- | --- |
| `q` | quit |
| `?` | help overlay |
| `s` | start the service |
| `S` | stop the service |
| `r` | restart the service |
| `R` | reload the rule set |
| `g` | refresh the current view |
| `c` | edit the service configuration and apply it with `config.set` |
| `/` | focus the filter or search box of the current view |
| `F` | in the logs view: filter by client address |
| arrows | move the cursor in the tables |
| `a` | in the rules view: block a domain |
| `k` | in the rules view: keep a domain (a KEEP exception) |
| `d` | in the rules view: delete the selected rule |
| `d` | in the router view: deploy the rule set to the router |
| `d` | on the other views: look up the names of the devices in the query log |
| `b` | in the router view: roll back to the previous file on the router |
| `ctrl+p` | open the command palette, where the theme can be changed |

The same actions are available as buttons: the service and router views put
them in a row at the top, and the rules view has Block, Keep and Delete
next to the search box.

Socket errors never take the interface down, they are reported in the status
line. When the service is stopped the interface keeps working and offers to
start it.

## Theme

The interface starts on **tokyo-night**, the theme Textual ships: its purple,
blue, orange, green, red and yellow over its deep blue background. The
palette lives in `src/toney/theme.py`, once, and is used twice: as Textual
theme variables for the stylesheet and as plain hex for the text the views
build.

`ctrl+p` opens the command palette, where the themes are listed. Picking one
redraws the cards and the log tables in the new colours. The choice is not
remembered: the interface starts on tokyo-night every time.

## Layout

The interface is built with Textual. The pieces that matter:

| File | What it holds |
| --- | --- |
| `src/toney/app.py` | the application, the header, the status line and the key bindings |
| `src/toney/controller.py` | everything that talks to the service, with no terminal code in it |
| `src/toney/theme.py` | the colours, as Textual theme variables and as plain hex |
| `src/toney/toney.tcss` | the stylesheet |
| `src/toney/views/` | one module per view |

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The tests use an in-process fake server and never need a running dnsguard.
The interface tests drive the real widgets through the Textual test driver,
so the key bindings are exercised for real.

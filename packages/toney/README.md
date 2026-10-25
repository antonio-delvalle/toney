# Toney

Toney is a terminal UI that manages the **dnsguard** DNS filtering service.
The service is a separate program; Toney only ever talks to it through the
Unix domain socket control protocol: one JSON object per line in each
direction.
Toney needs Python 3.10 or newer and the standard library only.

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
  "rules_file": "~/.config/toney/rules.blocklist"
}
```

A missing or unreadable file is not an error, the defaults above are used.

`rules_file` is where the rules editor writes. The editor rebuilds the rule
set from the rules the service reports, writes it to that path and hands the
path to the service with `rules.set`, so the change survives a restart.

## Views and keys

The views are the dashboard, the logs, the rules, the service screen and the
router. `Tab` switches between them, `1` to `5` jump straight to one of them.

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
| `/` | filter the logs or search the rules |
| `F` | filter the logs by client address |
| arrows | scroll the logs, pick a service action |
| `a` | in the rules view: block a domain |
| `k` | in the rules view: keep a domain (a KEEP exception) |
| `d` | in the rules view: delete the selected rule |
| `d` | in the router view: deploy the rule set to the router |
| `b` | in the router view: roll back to the previous file on the router |

Socket errors never take the interface down, they are reported in the status
line. When the service is stopped the interface keeps working and offers to
start it.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The tests use an in-process fake server and never need a running dnsguard.
